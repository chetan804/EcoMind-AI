"""Waste reports: authorization, validation, listing, idempotency and the review workflow."""

from __future__ import annotations

import datetime as dt
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.fixtures.api import ClientFactory, bearer, create_user, login

REPORTS = "/api/v1/waste-reports"


@dataclass
class Env:
    client: TestClient
    engine: Engine
    citizen: dict[str, str]
    other: dict[str, str]
    collector: dict[str, str]
    manager: dict[str, str]
    citizen_id: uuid.UUID


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    client = make_client()
    spec = {
        "citizen": ("citizen@example.org", ("citizen",)),
        "other": ("other@example.org", ("citizen",)),
        "collector": ("collector@example.org", ("collector",)),
        "manager": ("manager@example.org", ("manager",)),
    }
    ids: dict[str, uuid.UUID] = {}
    headers: dict[str, dict[str, str]] = {}
    for name, (email, roles) in spec.items():
        ids[name] = create_user(db_engine, email=email, roles=roles)
        headers[name] = bearer(login(client, email)["access_token"])
    return Env(
        client=client,
        engine=db_engine,
        citizen=headers["citizen"],
        other=headers["other"],
        collector=headers["collector"],
        manager=headers["manager"],
        citizen_id=ids["citizen"],
    )


def make_report(
    env: Env, headers: dict[str, str] | None = None, **overrides: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": "Overflowing bin near the market"}
    body.update(overrides)
    response = env.client.post(REPORTS, json=body, headers=headers or env.citizen)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


# ---------------------------------------------------------------- authentication and roles


def test_every_endpoint_requires_authentication(env: Env) -> None:
    some_id = uuid.uuid4()
    calls: list[Callable[[], Any]] = [
        lambda: env.client.get(REPORTS),
        lambda: env.client.post(REPORTS, json={"title": "abc"}),
        lambda: env.client.get(f"{REPORTS}/{some_id}"),
        lambda: env.client.post(f"{REPORTS}/{some_id}/review", json={"status": "verified"}),
        lambda: env.client.post(f"{REPORTS}/media", content=b"x"),
        lambda: env.client.get(f"{REPORTS}/media/{some_id}/content"),
    ]
    for call in calls:
        response = call()
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"


def test_roles_without_the_permission_are_forbidden(env: Env) -> None:
    # collectors can read reports but not submit them; citizens cannot review
    assert env.client.post(REPORTS, json={"title": "abc"}, headers=env.collector).status_code == 403
    assert (
        env.client.post(f"{REPORTS}/media", content=b"x", headers=env.collector).status_code == 403
    )
    report = make_report(env)
    review = env.client.post(
        f"{REPORTS}/{report['id']}/review", json={"status": "verified"}, headers=env.citizen
    )
    assert review.status_code == 403
    assert "waste_reports" not in review.text  # does not name the missing permission


def test_a_user_with_no_read_permission_cannot_list(env: Env, db_engine: Engine) -> None:
    create_user(db_engine, email="norole@example.org", roles=())
    headers = bearer(login(env.client, "norole@example.org")["access_token"])
    assert env.client.get(REPORTS, headers=headers).status_code == 403


# ------------------------------------------------------------------------------ creation


def test_create_returns_the_stored_report_and_audits_it(env: Env) -> None:
    response = env.client.post(
        REPORTS,
        json={
            "title": "  Illegal dumping behind the school  ",
            "description": "Mixed construction waste",
            "address_text": "12 Lake Road",
            "latitude": "17.385044",
            "longitude": "78.486671",
            "estimated_weight_kg": "42.5",
        },
        headers=env.citizen,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Illegal dumping behind the school"  # trimmed
    assert body["status"] == "submitted"
    assert body["reporter_id"] == str(env.citizen_id)
    assert body["media"] == []
    assert float(body["estimated_weight_kg"]) == 42.5
    with env.engine.connect() as conn:
        row = conn.execute(
            text("SELECT actor_id, entity_id FROM audit_logs WHERE action='waste_report.created'")
        ).one()
    assert (row.actor_id, str(row.entity_id)) == (env.citizen_id, body["id"])


def test_reporter_cannot_be_chosen_by_the_client(env: Env) -> None:
    response = env.client.post(
        REPORTS,
        json={"title": "abc", "reporter_id": str(uuid.uuid4()), "status": "verified"},
        headers=env.citizen,
    )
    assert response.status_code == 422  # unknown fields are rejected, not ignored


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "ab"},
        {"title": "x" * 201},
        {"title": "   "},
        {"title": "abc", "latitude": "10"},
        {"title": "abc", "longitude": "10"},
        {"title": "abc", "latitude": "91", "longitude": "0"},
        {"title": "abc", "latitude": "0", "longitude": "181"},
        {"title": "abc", "estimated_weight_kg": "-1"},
        {"title": "abc", "estimated_weight_kg": "100001"},
        {"title": "abc", "description": "d" * 4001},
        {"title": "abc", "media_ids": [str(uuid.uuid4())] * 2},
        {"title": "abc", "media_ids": [str(uuid.uuid4()) for _ in range(6)]},
        {"title": "abc", "media_ids": ["not-a-uuid"]},
    ],
)
def test_invalid_bodies_are_rejected_with_the_error_envelope(
    env: Env, payload: dict[str, Any]
) -> None:
    response = env.client.post(REPORTS, json=payload, headers=env.citizen)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    with env.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM waste_reports")).scalar_one() == 0


# -------------------------------------------------------------------------------- visibility


def test_citizens_only_see_their_own_reports_and_others_look_missing(env: Env) -> None:
    mine = make_report(env, title="Mine")
    theirs = make_report(env, env.other, title="Theirs")

    listed = env.client.get(REPORTS, headers=env.citizen).json()
    assert [r["id"] for r in listed["items"]] == [mine["id"]]
    assert listed["total"] == 1

    assert env.client.get(f"{REPORTS}/{mine['id']}", headers=env.citizen).status_code == 200
    hidden = env.client.get(f"{REPORTS}/{theirs['id']}", headers=env.citizen)
    unknown = env.client.get(f"{REPORTS}/{uuid.uuid4()}", headers=env.citizen)
    # 404 for both: a caller cannot tell "exists but not yours" from "does not exist"
    assert hidden.status_code == unknown.status_code == 404
    assert hidden.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_staff_with_read_all_see_everything_and_can_filter_to_their_own(env: Env) -> None:
    a = make_report(env, title="Report A")
    b = make_report(env, env.other, title="Report B")
    for staff in (env.collector, env.manager):
        everyone = env.client.get(REPORTS, headers=staff).json()
        assert {r["id"] for r in everyone["items"]} == {a["id"], b["id"]}
        assert env.client.get(f"{REPORTS}/{b['id']}", headers=staff).status_code == 200
    assert env.client.get(f"{REPORTS}?mine=true", headers=env.manager).json()["total"] == 0
    assert env.client.get(f"{REPORTS}?mine=true", headers=env.citizen).json()["total"] == 1


# ---------------------------------------------------------------------- listing mechanics


def test_pagination_is_stable_complete_and_bounded(env: Env) -> None:
    created = [make_report(env, title=f"Report {i:02d}") for i in range(7)]
    seen: list[str] = []
    for page in (1, 2, 3, 4):
        body = env.client.get(f"{REPORTS}?page={page}&page_size=3", headers=env.manager).json()
        assert body["total"] == 7 and body["page"] == page and body["page_size"] == 3
        seen += [r["id"] for r in body["items"]]
    assert len(seen) == 7 and set(seen) == {r["id"] for r in created}  # no repeat, no gap
    for bad in ("page=0", "page_size=0", "page_size=101", "page=abc"):
        assert env.client.get(f"{REPORTS}?{bad}", headers=env.manager).status_code == 422


def test_sorting_by_title_both_directions(env: Env) -> None:
    for title in ("banana", "Apple", "cherry"):
        make_report(env, title=title)
    asc = env.client.get(f"{REPORTS}?sort_by=title&order=asc", headers=env.manager).json()
    desc = env.client.get(f"{REPORTS}?sort_by=title&order=desc", headers=env.manager).json()
    assert [r["title"] for r in asc["items"]] == ["Apple", "banana", "cherry"]  # case-insensitive
    assert [r["title"] for r in desc["items"]] == ["cherry", "banana", "Apple"]
    assert env.client.get(f"{REPORTS}?sort_by=password", headers=env.manager).status_code == 422
    assert env.client.get(f"{REPORTS}?order=sideways", headers=env.manager).status_code == 422


def test_filter_by_status(env: Env) -> None:
    first = make_report(env, title="One")
    make_report(env, title="Two")
    env.client.post(
        f"{REPORTS}/{first['id']}/review", json={"status": "under_review"}, headers=env.manager
    )
    body = env.client.get(f"{REPORTS}?status=under_review", headers=env.manager).json()
    assert [r["id"] for r in body["items"]] == [first["id"]]
    assert env.client.get(f"{REPORTS}?status=bogus", headers=env.manager).status_code == 422


def test_search_matches_text_fields_and_treats_wildcards_literally(env: Env) -> None:
    make_report(env, title="Plastic bottles", description="near the river")
    make_report(env, title="Sofa", address_text="Riverside Avenue")
    make_report(env, title="100% cotton rags")
    make_report(env, title="Tyre_pile")

    def titles(query: str) -> set[str]:
        body = env.client.get(REPORTS, params={"q": query}, headers=env.manager).json()
        return {r["title"] for r in body["items"]}

    assert titles("RIVER") == {"Plastic bottles", "Sofa"}  # description + address, any case
    assert titles("100%") == {"100% cotton rags"}  # '%' is not "match anything"
    assert titles("%") == {"100% cotton rags"}
    assert titles("_") == {"Tyre_pile"}  # '_' is not "any one character"
    assert titles("nothing-matches-this") == set()
    assert env.client.get(REPORTS, params={"q": "x" * 101}, headers=env.manager).status_code == 422


def test_search_cannot_be_used_for_sql_injection(env: Env) -> None:
    make_report(env, title="Harmless")
    body = env.client.get(REPORTS, params={"q": "' OR '1'='1' --"}, headers=env.manager).json()
    assert body["total"] == 0
    assert env.client.get(REPORTS, headers=env.manager).json()["total"] == 1


def test_date_range_filter(env: Env) -> None:
    old = make_report(env, title="Old")
    make_report(env, title="Recent")
    with env.engine.begin() as conn:
        conn.execute(
            text("UPDATE waste_reports SET reported_at = now() - interval '10 days' WHERE id=:i"),
            {"i": old["id"]},
        )
    cutoff = (dt.datetime.now(dt.UTC) - dt.timedelta(days=2)).isoformat()
    recent = env.client.get(REPORTS, params={"reported_from": cutoff}, headers=env.manager).json()
    assert [r["title"] for r in recent["items"]] == ["Recent"]
    older = env.client.get(REPORTS, params={"reported_to": cutoff}, headers=env.manager).json()
    assert [r["title"] for r in older["items"]] == ["Old"]
    backwards = env.client.get(
        REPORTS,
        params={"reported_from": dt.datetime.now(dt.UTC).isoformat(), "reported_to": cutoff},
        headers=env.manager,
    )
    assert backwards.status_code == 400


# ----------------------------------------------------------------------------- idempotency


def _post_keyed(env: Env, key: str, headers: dict[str, str] | None = None, **body: Any) -> Any:
    payload = {"title": "Dumped sofa", **body}
    return env.client.post(
        REPORTS, json=payload, headers={**(headers or env.citizen), "Idempotency-Key": key}
    )


def test_a_retry_with_the_same_key_returns_the_original_report(env: Env) -> None:
    first = _post_keyed(env, "retry-key-0001")
    again = _post_keyed(env, "retry-key-0001")
    assert first.status_code == 201 and "idempotent-replayed" not in first.headers
    assert again.status_code == 200 and again.headers["idempotent-replayed"] == "true"
    assert again.json() == first.json()
    with env.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM waste_reports")).scalar_one() == 1
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_logs WHERE action='waste_report.created'")
            ).scalar_one()
            == 1
        )


def test_reusing_a_key_with_a_different_body_is_a_conflict_not_a_silent_replay(env: Env) -> None:
    assert _post_keyed(env, "retry-key-0002").status_code == 201
    clash = _post_keyed(env, "retry-key-0002", description="changed")
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "idempotency_key_reused"
    with env.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM waste_reports")).scalar_one() == 1


def test_keys_are_scoped_to_the_user(env: Env) -> None:
    mine = _post_keyed(env, "shared-key-0003")
    theirs = _post_keyed(env, "shared-key-0003", headers=env.other)
    assert mine.status_code == theirs.status_code == 201
    assert mine.json()["id"] != theirs.json()["id"]
    assert theirs.json()["reporter_id"] != mine.json()["reporter_id"]


@pytest.mark.parametrize("key", ["short", "has space in it", "semi;colon-key", "x" * 65, "é" * 10])
def test_malformed_idempotency_keys_are_rejected(env: Env, key: str) -> None:
    try:
        response = _post_keyed(env, key)
    except UnicodeEncodeError:  # header values must be latin-1 on the wire
        return
    assert response.status_code == 400


def test_without_a_key_every_request_creates_a_new_report(env: Env) -> None:
    make_report(env)
    make_report(env)
    assert env.client.get(REPORTS, headers=env.citizen).json()["total"] == 2


def test_concurrent_requests_with_one_key_create_exactly_one_report(env: Env) -> None:
    results: list[Any] = []
    barrier = threading.Barrier(2)

    def submit() -> None:
        barrier.wait()
        results.append(_post_keyed(env, "race-key-000004"))

    threads = [threading.Thread(target=submit) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(r.status_code for r in results) == [200, 201]
    assert results[0].json()["id"] == results[1].json()["id"]
    with env.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM waste_reports")).scalar_one() == 1


# -------------------------------------------------------------------------------- review


def _review(env: Env, report_id: str, status: str, **extra: Any) -> Any:
    return env.client.post(
        f"{REPORTS}/{report_id}/review", json={"status": status, **extra}, headers=env.manager
    )


def test_review_workflow_follows_the_state_machine_and_is_audited(env: Env) -> None:
    report = make_report(env)
    for target in ("under_review", "verified", "closed"):
        response = _review(env, report["id"], target)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target
    with env.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT changes FROM audit_logs WHERE action='waste_report.status_changed' "
                "ORDER BY occurred_at, id"
            )
        ).all()
    assert [(r.changes["from"], r.changes["to"]) for r in rows] == [
        ("submitted", "under_review"),
        ("under_review", "verified"),
        ("verified", "closed"),
    ]
    # the citizen sees the outcome of the review
    mine = env.client.get(f"{REPORTS}/{report['id']}", headers=env.citizen).json()
    assert mine["status"] == "closed"


@pytest.mark.parametrize(
    ("setup", "target"),
    [
        ([], "closed"),  # submitted -> closed is not allowed
        ([], "submitted"),  # not a legal target at all
        (["verified"], "rejected"),
        (["verified"], "under_review"),
        (["rejected"], "verified"),
        (["verified", "closed"], "verified"),
        (["under_review"], "under_review"),
    ],
)
def test_illegal_transitions_are_409_and_change_nothing(
    env: Env, setup: list[str], target: str
) -> None:
    report = make_report(env)
    for step in setup:
        reason = {"reason": "does not qualify"} if step == "rejected" else {}
        assert _review(env, report["id"], step, **reason).status_code == 200
    before = env.client.get(f"{REPORTS}/{report['id']}", headers=env.manager).json()["status"]
    response = _review(env, report["id"], target, reason="x-reason")
    assert response.status_code in (409, 422)
    if response.status_code == 409:
        assert response.json()["error"]["code"] == "invalid_status_transition"
    after = env.client.get(f"{REPORTS}/{report['id']}", headers=env.manager).json()["status"]
    assert after == before


def test_rejecting_requires_a_reason_and_records_it(env: Env) -> None:
    report = make_report(env)
    assert _review(env, report["id"], "rejected").status_code == 422
    assert _review(env, report["id"], "rejected", reason="  ").status_code == 422
    assert (
        _review(env, report["id"], "rejected", reason="Duplicate of another report").status_code
        == 200
    )
    with env.engine.connect() as conn:
        changes = conn.execute(
            text("SELECT changes FROM audit_logs WHERE action='waste_report.status_changed'")
        ).scalar_one()
    assert changes["reason"] == "Duplicate of another report"


def test_review_of_an_unknown_report_is_404_and_extra_fields_are_rejected(env: Env) -> None:
    assert _review(env, str(uuid.uuid4()), "verified").status_code == 404
    report = make_report(env)
    response = env.client.post(
        f"{REPORTS}/{report['id']}/review",
        json={"status": "verified", "reporter_id": str(uuid.uuid4())},
        headers=env.manager,
    )
    assert response.status_code == 422


def test_concurrent_reviews_apply_exactly_one_transition(env: Env) -> None:
    report = make_report(env)
    results: list[Any] = []
    barrier = threading.Barrier(2)

    def verify() -> None:
        barrier.wait()
        results.append(_review(env, report["id"], "verified"))

    threads = [threading.Thread(target=verify) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(r.status_code for r in results) == [200, 409]  # row lock serialises them
    with env.engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM audit_logs WHERE action='waste_report.status_changed'")
        ).scalar_one()
    assert count == 1


def test_database_rejects_a_key_without_fingerprint(env: Env) -> None:
    with env.engine.begin() as conn, pytest.raises(Exception, match="idempotency_complete"):
        conn.execute(
            text(
                "INSERT INTO waste_reports (reporter_id, title, idempotency_key) "
                "VALUES (:u, 'abc', 'orphan-key-001')"
            ),
            {"u": env.citizen_id},
        )
