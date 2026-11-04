"""The synthetic Hyderabad dataset generator (scripts/demo/synthetic).

Runs the smallest profile against a migrated scratch database and checks what matters for trust:
it is deterministic, labelled, resumable, idempotent, internally consistent (the same checks the
CLI's `verify` runs), refuses to run where it should not, and cleans up only its own rows.
"""

from __future__ import annotations

import datetime as dt
import importlib
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from sqlalchemy import Engine, text

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts" / "demo"
ANCHOR = dt.date(2026, 11, 4)
PREFIX = "53594e54-"


@pytest.fixture(scope="module")
def synth() -> Any:
    sys.path.insert(0, str(SCRIPTS))
    try:
        mods = {
            n: importlib.import_module(f"synthetic.{n}")
            for n in ("loader", "world", "profiles", "ids", "days")
        }
    finally:
        sys.path.remove(str(SCRIPTS))
    return type("Synth", (), mods)


@pytest.fixture
def dsn(db_engine: Engine) -> str:
    return db_engine.url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://", 1
    )


@pytest.fixture
def conn(dsn: str) -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(dsn)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def world(synth: Any) -> Any:
    return synth.world.World.build(42, synth.profiles.PROFILES["test"], ANCHOR)


def committed_count(dsn: str, sql: str) -> int:
    """Count through a separate connection, so only COMMITTED rows are seen (a rollback must show)."""
    other = psycopg.connect(dsn)
    try:
        row = other.execute(sql).fetchone()
    finally:
        other.close()
    assert row is not None
    return int(row[0])


def count(conn: psycopg.Connection, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    assert row is not None
    return int(row[0])


def test_every_stored_column_exists_and_every_required_column_is_filled(
    synth: Any, conn: psycopg.Connection
) -> None:
    for table in synth.loader.COLUMNS:
        stored = set(synth.loader.stored_columns(table))
        rows = conn.execute(
            "select column_name, is_nullable, column_default from information_schema.columns where table_schema='public' and table_name=%s",
            (table,),
        ).fetchall()
        real = {r[0] for r in rows}
        assert stored <= real, (table, stored - real)
        required = {r[0] for r in rows if r[1] == "NO" and r[2] is None}
        assert required <= stored, (table, required - stored)


def test_generation_is_deterministic_and_labelled(synth: Any, world: Any) -> None:
    other = synth.world.World.build(42, synth.profiles.PROFILES["test"], ANCHOR)
    a = synth.days.Simulator(world).day(dt.date(2026, 10, 14))
    b = synth.days.Simulator(other).day(dt.date(2026, 10, 14))
    assert a == b and sum(len(v) for v in a.values()) > 10
    reseeded = synth.days.Simulator(
        synth.world.World.build(7, synth.profiles.PROFILES["test"], ANCHOR)
    ).day(dt.date(2026, 10, 14))
    assert {row[0] for row in reseeded["collection_tasks"]}.isdisjoint(
        {row[0] for row in a["collection_tasks"]}
    )
    for rows in a.values():
        for row in rows:
            assert str(row[0]).startswith(PREFIX)


def test_load_is_consistent_idempotent_and_matches_the_plan(
    synth: Any, conn: psycopg.Connection, world: Any, dsn: str
) -> None:
    quiet = lambda _msg: None  # noqa: E731
    synth.loader.guard(conn, world, allow_existing=False, allow_remote=False)
    synth.loader.load_dimensions(conn, world)
    totals = synth.loader.load(conn, world, quiet)
    assert totals == synth.loader.count_rows(world)
    # durable: visible to another connection, not just inside the loading transaction
    assert (
        committed_count(
            dsn, f"select count(*) from collection_tasks where id::text like '{PREFIX}%'"
        )
        == totals["collection_tasks"]
    )
    assert committed_count(dsn, f"select count(*) from users where id::text like '{PREFIX}%'") > 0
    failures = [(name, bad) for name, bad in synth.loader.run_checks(conn) if bad]
    assert failures == []
    # fully populated chain: reports, tasks, routes, recovery, passports, rewards, notifications
    for table in (
        "waste_reports",
        "collection_tasks",
        "route_plans",
        "recovery_records",
        "material_passports",
        "custody_events",
        "reward_ledger_entries",
        "notifications",
        "community_incidents",
    ):
        assert totals[table] > 0, table
    before = {t: total for t, total, _ in synth.loader.table_counts(conn)}
    # a second run changes nothing, including the dimension rows
    assert not any(synth.loader.load_dimensions(conn, world).values())
    assert sum(synth.loader.load(conn, world, quiet).values()) == 0
    assert {t: total for t, total, _ in synth.loader.table_counts(conn)} == before
    # every synthetic user is a labelled, reserved-domain account that cannot sign in
    assert (
        count(
            conn,
            f"select count(*) from users where id::text like '{PREFIX}%' and (email not like '%@synthetic.example.org' or full_name not like '%(demo)')",
        )
        == 0
    )


def test_an_interrupted_load_resumes_to_the_same_result(
    synth: Any, conn: psycopg.Connection, world: Any, monkeypatch: pytest.MonkeyPatch, dsn: str
) -> None:
    quiet = lambda _msg: None  # noqa: E731
    synth.loader.load_dimensions(conn, world)
    days = list(synth.loader.days_range(world))
    monkeypatch.setattr(synth.loader, "days_range", lambda _w: iter(days[:25]))
    synth.loader.load(conn, world, quiet)
    partial = committed_count(dsn, "select count(*) from collection_tasks")
    monkeypatch.undo()
    synth.loader.load(conn, world, quiet)
    full = committed_count(dsn, "select count(*) from collection_tasks")
    assert 0 < partial < full == synth.loader.count_rows(world)["collection_tasks"]
    assert [name for name, bad in synth.loader.run_checks(conn) if bad] == []


def test_verification_catches_corruption(synth: Any, conn: psycopg.Connection, world: Any) -> None:
    quiet = lambda _msg: None  # noqa: E731
    synth.loader.load_dimensions(conn, world)
    synth.loader.load(conn, world, quiet)
    conn.execute(
        "update material_passports set weight_kg = weight_kg + 1 where id::text like %s",
        (PREFIX + "%",),
    )
    conn.execute(
        "update fleet_vehicles set status = 'maintenance' where id::text like %s", (PREFIX + "%",)
    )
    conn.execute("update recovery_records set recovered_weight_kg = input_weight_kg where false")
    conn.commit()
    failed = {name for name, bad in synth.loader.run_checks(conn) if bad}
    assert "passport weight equals the linked recovery record's recovered weight" in failed
    assert "vehicles used by a crew are available (not in maintenance or retired)" in failed


def test_safety_guards(
    synth: Any, conn: psycopg.Connection, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    refused = synth.loader.Refused
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(refused, match="production"):
        synth.loader.guard(conn, world, allow_existing=True, allow_remote=True)
    monkeypatch.setenv("ENVIRONMENT", "local")
    # real operational data present: refused unless explicitly allowed
    conn.execute(
        "insert into facilities (code, name, facility_type) values ('REAL-1', 'A genuine depot', 'depot')"
    )
    conn.commit()
    with pytest.raises(refused, match="non-synthetic"):
        synth.loader.guard(conn, world, allow_existing=False, allow_remote=False)
    synth.loader.guard(conn, world, allow_existing=True, allow_remote=False)
    # a different dataset (other seed) is never mixed in
    synth.loader.load_dimensions(conn, world)
    other = synth.world.World.build(99, synth.profiles.PROFILES["test"], ANCHOR)
    with pytest.raises(refused, match="different synthetic dataset"):
        synth.loader.guard(conn, other, allow_existing=True, allow_remote=False)


def test_cleanup_removes_only_synthetic_rows(
    synth: Any, conn: psycopg.Connection, world: Any, db_engine: Engine, dsn: str
) -> None:
    quiet = lambda _msg: None  # noqa: E731
    real_user = uuid.uuid4()
    with db_engine.begin() as sa:
        sa.execute(
            text(
                "insert into users (id, email, password_hash, full_name) values (:i, 'real.person@example.org', 'x', 'Real Person')"
            ),
            {"i": real_user},
        )
        sa.execute(
            text(
                "insert into facilities (code, name, facility_type) values ('REAL-1', 'A genuine depot', 'depot')"
            )
        )
    synth.loader.load_dimensions(conn, world)
    synth.loader.load(conn, world, quiet)
    assert count(conn, f"select count(*) from users where id::text like '{PREFIX}%'") > 0
    deleted = synth.loader.cleanup(conn, allow_remote=False, progress=quiet)
    assert sum(deleted.values()) > 1000
    synthetic_left = [(t, s) for t, _, s in synth.loader.table_counts(conn) if s]
    assert synthetic_left == []
    # the deletion was committed (it is visible from another connection)
    assert committed_count(dsn, f"select count(*) from users where id::text like '{PREFIX}%'") == 0
    assert (
        committed_count(
            dsn, f"select count(*) from collection_tasks where id::text like '{PREFIX}%'"
        )
        == 0
    )
    assert count(conn, "select count(*) from users where email = 'real.person@example.org'") == 1
    assert count(conn, "select count(*) from facilities where code = 'REAL-1'") == 1
    # and a real row that points at a synthetic one blocks the cleanup instead of being orphaned
    synth.loader.load_dimensions(conn, world)
    synthetic_user = conn.execute(
        f"select id from users where id::text like '{PREFIX}%' limit 1"
    ).fetchone()
    assert synthetic_user is not None
    conn.execute(
        "insert into notifications (recipient_id, category, title) values (%s, 'system', 'A real notification')",
        (synthetic_user[0],),
    )
    conn.commit()
    with pytest.raises(synth.loader.Refused, match="reference synthetic rows"):
        synth.loader.cleanup(conn, allow_remote=False, progress=quiet)
    assert count(conn, f"select count(*) from users where id::text like '{PREFIX}%'") > 0
