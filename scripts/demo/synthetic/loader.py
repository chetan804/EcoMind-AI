"""Database side: guarded, resumable loading (COPY), integrity checks, counts and cleanup."""

from __future__ import annotations

import datetime as dt
import os
import time
from collections.abc import Callable, Iterator

import psycopg

from .days import TABLES, Simulator
from .ids import PREFIX_TEXT, sid
from .world import World

COLUMNS: dict[str, tuple[str, ...]] = {
    "zones": ("id", "code", "name", "zone_type", "description", "is_active", "created_at", "updated_at"),
    "facilities": ("id", "code", "name", "facility_type", "status", "address_line", "city", "region", "country_code", "daily_capacity_kg", "contact_email", "latitude", "longitude", "zone_id", "created_at", "updated_at"),
    "fleet_vehicles": ("id", "registration_number", "vehicle_type", "status", "capacity_kg", "home_facility_id", "created_at", "updated_at"),
    "users": ("id", "email", "password_hash", "full_name", "is_active", "last_login_at", "email_verified_at", "created_at", "updated_at"),
    "reward_items": ("id", "name", "description", "points_cost", "stock", "max_per_user", "active", "valid_until", "created_by_id", "created_at", "updated_at"),
    "waste_reports": ("id", "reporter_id", "status", "title", "description", "address_text", "estimated_weight_kg", "reported_at", "latitude", "longitude", "idempotency_key", "request_fingerprint", "created_at", "updated_at"),
    "collection_tasks": ("id", "waste_report_id", "destination_facility_id", "created_by_id", "title", "status", "priority", "address_text", "due_at", "notes", "latitude", "longitude", "created_at", "updated_at"),
    "collection_assignments": ("id", "collection_task_id", "assignee_id", "vehicle_id", "assigned_by_id", "assigned_at", "unassigned_at", "created_at", "updated_at"),
    "collection_task_status_history": ("id", "collection_task_id", "from_status", "to_status", "changed_by_id", "note", "created_at", "updated_at"),
    "collection_events": ("id", "collection_task_id", "event_type", "occurred_at", "recorded_by_id", "facility_id", "collected_weight_kg", "notes", "latitude", "longitude", "created_at", "updated_at"),
    "route_plans": ("id", "name", "planned_date", "status", "vehicle_id", "driver_id", "start_facility_id", "end_facility_id", "created_by_id", "total_distance_km", "estimated_duration_min", "optimizer", "created_at", "updated_at"),
    "route_stops": ("id", "route_plan_id", "sequence", "collection_task_id", "facility_id", "planned_arrival_at", "actual_arrival_at", "created_at", "updated_at"),
    "vehicle_location_events": ("id", "vehicle_id", "latitude", "longitude", "recorded_at", "received_at", "source", "quality", "accuracy_m", "speed_kph", "heading_deg", "sequence", "collection_task_id", "route_plan_id", "reported_by_id", "created_at", "updated_at"),
    "recovery_records": ("id", "facility_id", "material_category_id", "collection_task_id", "evidence_media_asset_id", "recovery_method", "input_weight_kg", "recovered_weight_kg", "processed_at", "created_by_id", "verification_status", "verified_by_id", "verified_at", "notes", "created_at", "updated_at"),
    "material_passports": ("id", "passport_code", "material_category_id", "status", "description", "weight_kg", "origin_collection_task_id", "recovery_record_id", "current_facility_id", "created_by_id", "created_at", "updated_at"),
    "custody_events": ("id", "material_passport_id", "sequence", "event_type", "occurred_at", "actor_id", "from_facility_id", "to_facility_id", "notes", "created_at", "updated_at"),
    "reward_ledger_entries": ("id", "user_id", "entry_type", "points", "impact_weight_kg", "source_type", "source_id", "reverses_entry_id", "created_by_id", "description", "created_at", "updated_at"),
    "reward_redemptions": ("id", "user_id", "item_id", "item_name", "points_spent", "code", "client_request_id", "status", "ledger_entry_id", "refund_entry_id", "fulfilled_by_id", "fulfilled_at", "note", "cancelled_by_id", "cancelled_at", "cancel_reason", "created_at", "updated_at"),
    "notifications": ("id", "recipient_id", "category", "title", "body", "entity_type", "entity_id", "read_at", "created_at", "updated_at"),
    "community_incidents": ("id", "reporter_id", "assigned_to_id", "photo_media_asset_id", "incident_type", "status", "title", "description", "address_text", "resolved_at", "resolution_notes", "latitude", "longitude", "created_at", "updated_at"),
    "marketplace_listings": ("id", "created_by_id", "facility_id", "title", "description", "category", "quantity", "unit", "condition", "pickup_city", "status", "published_at", "closed_at", "close_reason", "expires_at", "expiry_notice_sent_at", "outcome", "created_at", "updated_at"),
    "marketplace_requests": ("id", "listing_id", "requester_id", "message", "status", "decided_at", "created_at", "updated_at"),
}  # fmt: skip

# The row builders emit created_at/updated_at everywhere; these append-only tables have fewer columns.
NOT_STORED: dict[str, tuple[str, ...]] = {
    "collection_task_status_history": ("updated_at",),
    "collection_events": ("updated_at",),
    "vehicle_location_events": ("created_at", "updated_at"),
    "custody_events": ("updated_at",),
    "reward_ledger_entries": ("updated_at",),
    "notifications": ("updated_at",),
}

# Parents before children. Cleanup walks it backwards.
LOAD_ORDER = (
    "waste_reports", "collection_tasks", "collection_assignments", "collection_task_status_history",
    "collection_events", "route_plans", "route_stops", "vehicle_location_events", "recovery_records",
    "material_passports", "custody_events", "reward_ledger_entries", "reward_redemptions", "notifications",
    "community_incidents", "marketplace_listings", "marketplace_requests",
)  # fmt: skip
DIMENSION_ORDER = ("zones", "facilities", "fleet_vehicles", "users", "user_roles", "reward_items")
CLEANUP_ORDER = (*reversed(LOAD_ORDER), "reward_items", "user_roles", "users", "fleet_vehicles", "facilities", "zones")
assert set(LOAD_ORDER) == set(TABLES)

Progress = Callable[[str], None]


class Refused(RuntimeError):
    """The safety checks stopped the run; nothing was changed."""


def dsn_from_environment() -> str:
    for name in ("SYNTH_DSN", "DEMO_DSN"):
        if os.environ.get(name):
            return os.environ[name]
    url = os.environ.get("DATABASE_URL")
    if url:
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    raise Refused("Set SYNTH_DSN (or DEMO_DSN, or DATABASE_URL) to the database to fill.")


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=False)


def _scalar(conn: psycopg.Connection, sql: str, *params: object) -> int:
    row = conn.execute(sql, params or None).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def guard(conn: psycopg.Connection, world: World | None, *, allow_existing: bool, allow_remote: bool) -> None:
    if os.environ.get("ENVIRONMENT", "local").lower() in {"production", "prod", "staging"}:
        raise Refused("ENVIRONMENT says production/staging. Synthetic data is never loaded there.")
    host = conn.info.host or ""
    if not allow_remote and not (host.startswith("/") or host in {"localhost", "127.0.0.1", "::1", ""}):
        raise Refused(f"The database host {host!r} is not local. Pass --allow-remote only for a throw-away database.")
    real = _scalar(conn, f"select count(*) from collection_tasks where id::text not like '{PREFIX_TEXT}%'") + _scalar(
        conn, f"select count(*) from facilities where id::text not like '{PREFIX_TEXT}%'"
    )
    if real and not allow_existing:
        raise Refused(
            f"The database already holds {real} non-synthetic facilities/tasks. Use a fresh database, or pass "
            "--allow-existing-data to add the labelled synthetic dataset next to them (nothing is overwritten)."
        )
    if world is not None:
        stored = conn.execute(f"select description from zones where id::text like '{PREFIX_TEXT}%' limit 1").fetchone()
        if stored and not str(stored[0]).startswith(world.marker):
            raise Refused(
                "A different synthetic dataset is already loaded (" + str(stored[0]).split(". Approximate")[0]
                + "). Clean it up first, or use the same --seed/--profile/--anchor to resume it."
            )


def stored_columns(table: str) -> tuple[str, ...]:
    return tuple(c for c in COLUMNS[table] if c not in NOT_STORED.get(table, ()))


def _copy(conn: psycopg.Connection, table: str, rows: list[tuple[object, ...]]) -> None:
    cols = COLUMNS[table]
    keep = [i for i, c in enumerate(cols) if c not in NOT_STORED.get(table, ())]
    stored = [cols[i] for i in keep]
    with conn.cursor() as cur, cur.copy(f"COPY {table} ({', '.join(stored)}) FROM STDIN") as cp:
        for row in rows:
            if len(row) != len(cols):
                raise AssertionError(f"{table}: row has {len(row)} values, expected {len(cols)}: {row!r}")
            cp.write_row([row[i] for i in keep])


def _upsert(conn: psycopg.Connection, table: str, rows: list[tuple[object, ...]]) -> int:
    """Insert rows whose ids are not there yet (dimension tables, which may already be partly loaded)."""
    cols = ", ".join(COLUMNS[table])
    conn.execute(f"create temp table _stage (like {table} including defaults) on commit drop")
    _copy_into(conn, "_stage", COLUMNS[table], rows)
    cur = conn.execute(f"insert into {table} ({cols}) select {cols} from _stage on conflict (id) do nothing")
    added = cur.rowcount
    conn.execute("drop table _stage")
    return added


def _copy_into(conn: psycopg.Connection, target: str, cols: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
    with conn.cursor() as cur, cur.copy(f"COPY {target} ({', '.join(cols)}) FROM STDIN") as cp:
        for row in rows:
            cp.write_row(row)


def load_dimensions(conn: psycopg.Connection, world: World) -> dict[str, int]:
    added: dict[str, int] = {}
    pw = world.password_hash()
    users, roles = world.user_rows(pw)
    with conn.transaction():
        added["zones"] = _upsert(conn, "zones", world.zone_rows())
        added["facilities"] = _upsert(conn, "facilities", world.facility_rows())
        added["fleet_vehicles"] = _upsert(conn, "fleet_vehicles", world.vehicle_rows())
        added["users"] = _upsert(conn, "users", users)
        role_ids = dict(conn.execute("select name, id from roles").fetchall())
        missing = {name for _, name in roles} - set(role_ids)
        if missing:
            raise Refused(f"roles missing from the database ({sorted(missing)}); run the migrations first")
        conn.execute("create temp table _roles (user_id uuid, role_id uuid) on commit drop")
        _copy_into(conn, "_roles", ("user_id", "role_id"), [(u, role_ids[n]) for u, n in roles])
        cur = conn.execute("insert into user_roles (user_id, role_id) select user_id, role_id from _roles on conflict do nothing")
        added["user_roles"] = cur.rowcount
        added["reward_items"] = _upsert(conn, "reward_items", world.reward_item_rows())
    conn.commit()  # the reads in guard() opened an outer transaction; make the dimensions durable now
    return added


def days_range(world: World) -> Iterator[dt.date]:
    d = world.anchor - dt.timedelta(days=world.profile.days)
    end = world.anchor + dt.timedelta(days=2)
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def _fix_categories(out: dict[str, list[tuple[object, ...]]], categories: dict[str, object]) -> None:
    for table in ("recovery_records", "material_passports"):
        out[table] = [(*row[:2], categories[str(row[2])], *row[3:]) for row in out[table]]


def load(conn: psycopg.Connection, world: World, progress: Progress = print, *, commit_every: int = 1) -> dict[str, int]:
    """Generate every day; store the days that are not stored yet. Safe to interrupt and re-run."""
    categories = dict(conn.execute("select code, id from material_categories").fetchall())
    sim = Simulator(world)
    totals = {t: 0 for t in LOAD_ORDER}
    started = time.monotonic()
    skipped = loaded = 0
    for d in days_range(world):
        batch = sim.day(d)  # always generated, so the running state is identical on a resume
        first_task = sid(world.seed, "task", d.isoformat(), 0)
        if conn.execute("select 1 from collection_tasks where id = %s", (first_task,)).fetchone():
            skipped += 1
            continue
        _fix_categories(batch, categories)
        with conn.transaction():
            for table in LOAD_ORDER:
                if batch[table]:
                    _copy(conn, table, batch[table])
                    totals[table] += len(batch[table])
        loaded += 1
        if loaded % 15 == 0:
            rows = sum(totals.values())
            progress(f"  {d}  days loaded {loaded}, skipped {skipped}, rows {rows:,} ({rows / max(1e-9, time.monotonic() - started):,.0f}/s)")
    conn.commit()
    return totals


def count_rows(world: World) -> dict[str, int]:
    """Generate everything without a database and count rows per table (used by `plan`)."""
    sim = Simulator(world)
    totals = {t: 0 for t in LOAD_ORDER}
    for d in days_range(world):
        for table, rows in sim.day(d).items():
            totals[table] += len(rows)
    return totals


# --------------------------------------------------------------------------- reports and checks
def table_counts(conn: psycopg.Connection) -> list[tuple[str, int, int]]:
    """(table, total rows, synthetic rows) for every application table."""
    out = []
    names = [r[0] for r in conn.execute("select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1")]
    for name in names:
        if name == "alembic_version":
            continue
        has_id = _scalar(conn, "select count(*) from information_schema.columns where table_schema='public' and table_name=%s and column_name='id'", name)
        total = _scalar(conn, f'select count(*) from "{name}"')
        synthetic = _scalar(conn, f"select count(*) from \"{name}\" where id::text like '{PREFIX_TEXT}%'") if has_id else (
            _scalar(conn, f"select count(*) from \"{name}\" where user_id::text like '{PREFIX_TEXT}%'") if name == "user_roles" else 0
        )  # fmt: skip
        out.append((name, total, synthetic))
    return out


P = PREFIX_TEXT
# Each check counts the synthetic rows that BREAK a rule. All must return 0.
CHECKS: tuple[tuple[str, str], ...] = (
    ("synthetic accounts use only the reserved synthetic.example.org domain",
     f"select count(*) from users where id::text like '{P}%' and email not like '%@synthetic.example.org'"),
    ("no synthetic account can sign in with a known password (hashes are Argon2id of discarded secrets)",
     f"select count(*) from users where id::text like '{P}%' and password_hash not like '$argon2id$%'"),
    ("every synthetic task has a status-history trail that ends in its current status",
     f"""select count(*) from collection_tasks t where t.id::text like '{P}%' and (
         select h.to_status from collection_task_status_history h where h.collection_task_id = t.id
         order by h.created_at desc, h.id desc limit 1) is distinct from t.status"""),
    ("history timestamps never run backwards",
     f"""select count(*) from (select collection_task_id, created_at, lag(created_at) over (partition by collection_task_id order by created_at, id) prev
         from collection_task_status_history where collection_task_id::text like '{P}%') x where prev > created_at"""),
    ("completed tasks have one collected event with a weight; failed ones have a skipped event; cancelled have none",
     f"""select count(*) from collection_tasks t where t.id::text like '{P}%' and (
         (t.status='completed' and (select count(*) from collection_events e where e.collection_task_id=t.id and e.event_type='collected' and e.collected_weight_kg > 0) <> 1)
      or (t.status='failed' and (select count(*) from collection_events e where e.collection_task_id=t.id and e.event_type='skipped') <> 1)
      or (t.status in ('cancelled','pending','assigned') and exists (select 1 from collection_events e where e.collection_task_id=t.id)))"""),
    ("assigned and in-progress tasks still have their active assignment",
     f"""select count(*) from collection_tasks t where t.id::text like '{P}%' and t.status in ('assigned','in_progress')
         and not exists (select 1 from collection_assignments a where a.collection_task_id=t.id and a.unassigned_at is null)"""),
    ("a collected load never exceeds the capacity of the assigned vehicle",
     f"""select count(*) from collection_events e join collection_assignments a on a.collection_task_id=e.collection_task_id
         join fleet_vehicles v on v.id=a.vehicle_id where e.collection_task_id::text like '{P}%' and e.event_type in ('collected','delivered_to_facility')
         and e.collected_weight_kg > v.capacity_kg"""),
    ("vehicles used by a crew are available (not in maintenance or retired)",
     f"""select count(*) from collection_assignments a join fleet_vehicles v on v.id=a.vehicle_id
         where a.id::text like '{P}%' and v.status <> 'available'"""),
    ("route stops are numbered 1..n without gaps",
     f"""select count(*) from (select route_plan_id, count(*) n, max(sequence) m, min(sequence) lo from route_stops where route_plan_id::text like '{P}%'
         group by route_plan_id) s where n <> m or lo <> 1"""),
    ("a task appears on at most one route stop",
     f"select count(*) from (select collection_task_id from route_stops where collection_task_id::text like '{P}%' group by 1 having count(*) > 1) s"),
    ("a route's recorded distance is straight-line only and no estimated duration or optimizer is claimed",
     f"select count(*) from route_plans where id::text like '{P}%' and (estimated_duration_min is not null or optimizer is not null)"),
    ("simulated GPS points carry the simulator source and sit before the end of the data",
     f"select count(*) from vehicle_location_events where id::text like '{P}%' and (source <> 'simulator' or recorded_at > now())"),
    ("recovery never exceeds the input, and input never exceeds what the task collected",
     f"""select count(*) from recovery_records r join collection_events e on e.collection_task_id=r.collection_task_id and e.event_type='collected'
         where r.id::text like '{P}%' and (r.recovered_weight_kg > r.input_weight_kg or r.input_weight_kg > e.collected_weight_kg)"""),
    ("a verified/rejected record names a verifier and a time after processing",
     f"""select count(*) from recovery_records where id::text like '{P}%' and verification_status <> 'pending'
         and (verified_by_id is null or verified_at is null or verified_at < processed_at)"""),
    ("passport weight equals the linked recovery record's recovered weight",
     f"""select count(*) from material_passports p join recovery_records r on r.id=p.recovery_record_id
         where p.id::text like '{P}%' and p.weight_kg <> r.recovered_weight_kg"""),
    ("passport custody chains start with 'created', are numbered 1..n and never go back in time",
     f"""select count(*) from (select material_passport_id, count(*) n, max(sequence) m, min(sequence) lo,
         (array_agg(event_type order by sequence))[1] first_type from custody_events where material_passport_id::text like '{P}%' group by 1) c
         where n <> m or lo <> 1 or first_type <> 'created'"""),
    ("custody timestamps are ordered by sequence",
     f"""select count(*) from (select occurred_at, lag(occurred_at) over (partition by material_passport_id order by sequence) prev
         from custody_events where material_passport_id::text like '{P}%') x where prev > occurred_at"""),
    ("a recovered passport has a 'verified' event and a verified record; an in-processing one does not",
     f"""select count(*) from material_passports p where p.id::text like '{P}%' and (
         (p.status='recovered') <> exists (select 1 from custody_events c where c.material_passport_id=p.id and c.event_type='verified'))"""),
    ("no synthetic citizen's points balance is ever negative (running sum in time order)",
     f"""select count(*) from (select sum(points) over (partition by user_id order by created_at, id) run from reward_ledger_entries
         where user_id::text like '{P}%') x where run < 0"""),
    ("every earned entry points back at a completed synthetic task with matching weight and 10 points per kg",
     f"""select count(*) from reward_ledger_entries l left join collection_events e on e.collection_task_id=l.source_id and e.event_type='collected'
         where l.id::text like '{P}%' and l.entry_type='earned' and (e.id is null or l.impact_weight_kg <> e.collected_weight_kg
         or l.points <> greatest(1, round(e.collected_weight_kg * 10)))"""),
    ("a cancelled redemption has a matching reversal; a reversal cancels exactly the redemption it names",
     f"""select count(*) from reward_redemptions r left join reward_ledger_entries f on f.id=r.refund_entry_id
         where r.id::text like '{P}%' and r.status='cancelled' and (f.id is null or f.points <> r.points_spent or f.reverses_entry_id <> r.ledger_entry_id)"""),
    ("reports closed by a collection have a completed task; tasks from a report point at a verified-or-closed report",
     f"""select count(*) from collection_tasks t join waste_reports r on r.id=t.waste_report_id where t.id::text like '{P}%'
         and ((t.status='completed' and r.status <> 'closed') or (t.status <> 'completed' and r.status <> 'verified'))"""),
    ("closed marketplace listings carry an outcome and a close time",
     f"""select count(*) from marketplace_listings l where l.id::text like '{P}%' and l.status='closed' and (l.outcome is null or l.closed_at is null)"""),
    ("no event, history, custody or ledger row is dated after the end of the data",
     f"""select (select count(*) from collection_events where id::text like '{P}%' and occurred_at > now())
         + (select count(*) from custody_events where id::text like '{P}%' and occurred_at > now())
         + (select count(*) from reward_ledger_entries where id::text like '{P}%' and created_at > now())"""),
)  # fmt: skip


def run_checks(conn: psycopg.Connection) -> list[tuple[str, int]]:
    results = []
    for name, sql in CHECKS:
        results.append((name, _scalar(conn, sql)))
    conn.rollback()
    return results


def _external_references(conn: psycopg.Connection) -> list[tuple[str, str, int]]:
    """Rows that are NOT synthetic but point at synthetic rows (cleanup must not orphan them)."""
    fks = conn.execute(
        """select c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text
           from pg_constraint c join pg_attribute a on a.attrelid=c.conrelid and a.attnum = c.conkey[1]
           where c.contype='f' and array_length(c.conkey,1)=1 and c.connamespace='public'::regnamespace"""
    ).fetchall()
    owned = set(CLEANUP_ORDER)
    found = []
    for child, column, parent in fks:
        if parent not in owned:
            continue
        has_id = _scalar(conn, "select count(*) from information_schema.columns where table_schema='public' and table_name=%s and column_name='id'", child)
        extra = f" and id::text not like '{P}%'" if has_id and child not in ("user_roles",) else " and false"
        n = _scalar(conn, f'select count(*) from "{child}" where "{column}"::text like \'{P}%\'{extra}')
        if n:
            found.append((child, column, n))
    return found


def cleanup(conn: psycopg.Connection, *, allow_remote: bool, progress: Progress = print) -> dict[str, int]:
    """Delete synthetic rows only (ids starting 53594e54-). Real rows are never touched."""
    guard(conn, None, allow_existing=True, allow_remote=allow_remote)
    external = _external_references(conn)
    if external:
        raise Refused("Real rows reference synthetic rows, so nothing was deleted: " + ", ".join(f"{t}.{c} ({n})" for t, c, n in external))
    superuser = conn.execute("select rolsuper from pg_roles where rolname = current_user").fetchone()
    if not superuser or not superuser[0]:
        raise Refused(
            "Several tables are append-only (database triggers refuse DELETE), so cleanup needs a superuser that may set "
            "session_replication_role. Run it as the local postgres user on a throw-away database."
        )
    deleted: dict[str, int] = {}
    with conn.transaction():
        conn.execute("set local session_replication_role = replica")  # only append-only triggers; order below keeps FKs valid
        for table in CLEANUP_ORDER:
            column = "user_id" if table == "user_roles" else "id"
            cur = conn.execute(f"delete from \"{table}\" where \"{column}\"::text like '{P}%'")
            deleted[table] = cur.rowcount
            progress(f"  deleted {cur.rowcount:>9,} from {table}")
    conn.commit()
    return deleted
