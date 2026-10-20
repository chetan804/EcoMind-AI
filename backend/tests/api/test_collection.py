"""Collection tasks: lifecycle, ownership, side effects, concurrency-relevant guards.

The workflow tests drive the real endpoints end to end: citizen reports waste, a manager
verifies it, schedules and assigns a task, the collector works it, and the outcome shows up in
the report, the reward ledger, the reporter's notifications and the audit trail.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.fixtures.api import ClientFactory, bearer, create_user, login

TASKS = "/api/v1/collection/tasks"
REPORTS = "/api/v1/waste-reports"
FLEET = "/api/v1/fleet/vehicles"


@dataclass
class Env:
    client: TestClient
    engine: Engine
    ids: dict[str, uuid.UUID]
    h: dict[str, dict[str, str]]


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    client = make_client()
    ids, heads = {}, {}
    for name, roles in (
        ("citizen", ("citizen",)),
        ("collector", ("collector",)),
        ("collector2", ("collector",)),
        ("operator", ("facility_operator",)),
        ("manager", ("manager",)),
    ):
        ids[name] = create_user(
            db_engine, email=f"{name}@example.org", roles=roles, full_name=f"Person {name}"
        )
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    return Env(client, db_engine, ids, heads)


def sql(env: Env, query: str, **params: Any) -> list[Any]:
    with env.engine.connect() as conn:
        return list(conn.execute(text(query), params).all())


def verified_report(env: Env, **overrides: Any) -> dict[str, Any]:
    body = {
        "title": "Overflowing bins near the market",
        "latitude": "17.385044",
        "longitude": "78.486671",
        "address_text": "Market Road",
        "estimated_weight_kg": "40",
    }
    body.update(overrides)
    created = env.client.post(REPORTS, json=body, headers=env.h["citizen"])
    assert created.status_code == 201, created.text
    report = created.json()
    review = env.client.post(
        f"{REPORTS}/{report['id']}/review", json={"status": "verified"}, headers=env.h["manager"]
    )
    assert review.status_code == 200, review.text
    return dict(review.json())


def new_task(env: Env, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"title": "Clear the dumping spot", "address_text": "Lane 4"}
    body.update(overrides)
    response = env.client.post(TASKS, json=body, headers=env.h["manager"])
    assert response.status_code == 201, response.text
    return dict(response.json())


def act(
    env: Env, who: str, task: dict[str, Any], verb: str, body: dict[str, Any] | None = None
) -> Any:
    return env.client.post(f"{TASKS}/{task['id']}/{verb}", json=body or {}, headers=env.h[who])


def assign(env: Env, task: dict[str, Any], who: str = "collector", **extra: Any) -> dict[str, Any]:
    response = act(env, "manager", task, "assign", {"assignee_id": str(env.ids[who]), **extra})
    assert response.status_code == 200, response.text
    return dict(response.json())


def facility(env: Env, code: str = "HYD-01", **extra: Any) -> dict[str, Any]:
    body = {"code": code, "name": "Hyderabad Centre", "facility_type": "processing_center", **extra}
    response = env.client.post("/api/v1/facilities", json=body, headers=env.h["manager"])
    assert response.status_code == 201, response.text
    return dict(response.json())


# --------------------------------------------------------------------------------- access
def test_authentication_and_authorization(env: Env) -> None:
    some = uuid.uuid4()
    for method, url in (
        ("get", TASKS),
        ("post", TASKS),
        ("get", f"{TASKS}/{some}"),
        ("post", f"{TASKS}/{some}/assign"),
        ("post", f"{TASKS}/{some}/start"),
        ("post", f"{TASKS}/{some}/complete"),
        ("post", f"{TASKS}/{some}/cancel"),
    ):
        assert getattr(env.client, method)(url).status_code == 401, (method, url)
    # citizens have no collection permission
    assert env.client.get(TASKS, headers=env.h["citizen"]).status_code == 403
    # collectors and operators can read, collectors cannot create/assign/cancel
    assert env.client.get(TASKS, headers=env.h["collector"]).status_code == 200
    assert env.client.get(TASKS, headers=env.h["operator"]).status_code == 200
    body = {"title": "x y z", "address_text": "somewhere"}
    assert env.client.post(TASKS, json=body, headers=env.h["collector"]).status_code == 403
    task = new_task(env)
    for verb, payload in (
        ("assign", {"assignee_id": str(env.ids["collector"])}),
        ("cancel", {"reason": "no longer needed"}),
        ("reschedule", {"due_at": "2099-01-01T00:00:00Z"}),
    ):
        assert act(env, "collector", task, verb, payload).status_code == 403
    # operators cannot work tasks
    assert act(env, "operator", task, "start").status_code == 403


# ---------------------------------------------------------------------------------- create
def test_create_from_verified_report_copies_location_and_blocks_duplicates(env: Env) -> None:
    report = verified_report(env)
    task = new_task(env, waste_report_id=report["id"], title=None, address_text=None)
    assert task["waste_report_id"] == report["id"]
    assert task["status"] == "pending"
    assert task["title"] == "Collect: Overflowing bins near the market"
    assert task["latitude"] == "17.385044" and task["address_text"] == "Market Road"
    assert [h["to_status"] for h in task["history"]] == ["pending"]
    dup = env.client.post(TASKS, json={"waste_report_id": report["id"]}, headers=env.h["manager"])
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "report_has_open_task"


def test_create_rejects_unverified_missing_and_unlocated(env: Env) -> None:
    created = env.client.post(
        REPORTS, json={"title": "Not yet reviewed"}, headers=env.h["citizen"]
    ).json()
    resp = env.client.post(TASKS, json={"waste_report_id": created["id"]}, headers=env.h["manager"])
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "report_not_verified"
    ghost = env.client.post(
        TASKS, json={"waste_report_id": str(uuid.uuid4())}, headers=env.h["manager"]
    )
    assert ghost.status_code == 422
    nowhere = env.client.post(TASKS, json={"title": "No place"}, headers=env.h["manager"])
    assert nowhere.status_code == 422
    for bad in (
        {"title": "ab", "address_text": "x"},
        {"title": "Fine title", "latitude": "10"},
        {"title": "Fine title", "address_text": "x", "due_at": "2026-10-20T10:00:00"},
        {"title": "Fine title", "address_text": "x", "due_at": "2001-01-01T00:00:00Z"},
        {"title": "Fine title", "address_text": "x", "priority": "asap"},
        {"title": "Fine title", "address_text": "x", "destination_facility_id": str(uuid.uuid4())},
        {"title": "Fine title", "address_text": "x", "extra": 1},
    ):
        assert env.client.post(TASKS, json=bad, headers=env.h["manager"]).status_code == 422, bad


# ------------------------------------------------------------------------------ lifecycle
def test_full_collection_journey_updates_report_ledger_notifications_and_audit(env: Env) -> None:
    report = verified_report(env)
    hub = facility(env)
    vehicle = env.client.post(
        FLEET,
        json={"registration_number": "TS 09 AB 1234", "vehicle_type": "van", "capacity_kg": 800},
        headers=env.h["manager"],
    ).json()
    task = new_task(
        env, waste_report_id=report["id"], priority="high", destination_facility_id=hub["id"]
    )

    assigned = assign(env, task, vehicle_id=vehicle["id"])
    assert assigned["status"] == "assigned"
    assert assigned["assignment"]["assignee_name"] == "Person collector"
    assert assigned["assignment"]["vehicle_registration"] == "TS 09 AB 1234"
    # the collector was told
    mine = sql(
        env,
        "select title, entity_id from notifications where recipient_id = :u",
        u=env.ids["collector"],
    )
    assert [row[0] for row in mine] == ["New collection task assigned"]
    assert (
        env.client.get(f"{FLEET}/{vehicle['id']}", headers=env.h["manager"]).json()[
            "active_task_count"
        ]
        == 1
    )

    # only the assignee (or a manager) works the task
    assert act(env, "collector2", task, "start").status_code == 403
    started = act(env, "collector", task, "start")
    assert started.status_code == 200 and started.json()["status"] == "in_progress"

    arrived = act(env, "collector", task, "events", {"event_type": "arrived"})
    assert arrived.status_code == 201
    assert [e["event_type"] for e in arrived.json()["events"]] == ["arrived"]
    assert act(env, "collector", task, "events", {"event_type": "collected"}).status_code == 422
    assert (
        act(env, "collector", task, "events", {"event_type": "delivered_to_facility"}).status_code
        == 422
    )

    done = act(
        env, "collector", task, "complete", {"collected_weight_kg": "37.5", "notes": "all picked"}
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "completed"
    assert body["collected_weight_kg"] == "37.500"
    assert [h["to_status"] for h in body["history"]] == [
        "pending",
        "assigned",
        "in_progress",
        "completed",
    ]
    assert body["assignment"]["unassigned_at"] is not None  # work ended
    assert body["events"][-1]["event_type"] == "collected"
    assert body["events"][-1]["facility_id"] == hub["id"]

    # report closed; reward recorded once with the policy (10 pts/kg * 37.5 = 375)
    assert (
        env.client.get(f"{REPORTS}/{report['id']}", headers=env.h["citizen"]).json()["status"]
        == "closed"
    )
    ledger = sql(
        env,
        "select entry_type, points, impact_weight_kg, source_type from reward_ledger_entries where user_id=:u",
        u=env.ids["citizen"],
    )
    assert len(ledger) == 1
    assert ledger[0][0] == "earned" and ledger[0][1] == 375 and str(ledger[0][2]) == "37.500"
    assert ledger[0][3] == "collection_task"
    reporter_notes = sql(
        env, "select title from notifications where recipient_id=:u", u=env.ids["citizen"]
    )
    assert [r[0] for r in reporter_notes] == ["Your reported waste was collected"]
    actions = [
        r[0]
        for r in sql(
            env,
            "select action from audit_logs where entity_type='collection_task' order by occurred_at",
        )
    ]
    assert actions == [
        "collection_task.created",
        "collection_task.assigned",
        "collection_task.started",
        "collection_task.event.arrived",
        "collection_task.completed",
    ]
    assert (
        env.client.get(f"{FLEET}/{vehicle['id']}", headers=env.h["manager"]).json()[
            "active_task_count"
        ]
        == 0
    )

    # terminal: nothing else can happen, and the reward is not duplicated
    assert act(env, "manager", task, "cancel", {"reason": "too late"}).status_code == 409
    assert act(env, "collector", task, "complete", {"collected_weight_kg": "5"}).status_code == 409
    assert sql(env, "select count(*) from reward_ledger_entries")[0][0] == 1


def test_failure_then_reschedule_then_success(env: Env) -> None:
    task = new_task(env)
    assign(env, task)
    # cannot fail before the collector is on the task? assigned -> failed is allowed (unreachable site)
    assert act(env, "collector", task, "start").status_code == 200
    failed = act(env, "collector", task, "fail", {"reason": "Gate locked, nobody on site"})
    assert failed.status_code == 200 and failed.json()["status"] == "failed"
    assert failed.json()["history"][-1]["note"] == "Gate locked, nobody on site"
    assert failed.json()["assignment"]["unassigned_at"] is not None
    # a failed task cannot be started again without being rescheduled
    assert act(env, "collector", task, "start").status_code == 409  # failed: must be rescheduled
    soon = (dt.datetime.now(dt.UTC) + dt.timedelta(days=1)).isoformat()
    resched = act(env, "manager", task, "reschedule", {"due_at": soon, "note": "retry tomorrow"})
    assert resched.status_code == 200
    assert resched.json()["status"] == "pending" and resched.json()["due_at"] is not None
    assign(env, task, "collector2")
    assert act(env, "collector2", task, "start").status_code == 200
    ok = act(env, "collector2", task, "complete", {"collected_weight_kg": "12"})
    assert ok.status_code == 200
    assert [h["to_status"] for h in ok.json()["history"]] == [
        "pending",
        "assigned",
        "in_progress",
        "failed",
        "pending",
        "assigned",
        "in_progress",
        "completed",
    ]
    # no report -> no reward row
    assert sql(env, "select count(*) from reward_ledger_entries")[0][0] == 0


def test_reassign_closes_previous_assignment_and_manager_can_cancel(env: Env) -> None:
    task = new_task(env)
    assign(env, task, "collector")
    second = assign(env, task, "collector2")
    assert second["assignment"]["assignee_name"] == "Person collector2"
    rows = sql(
        env, "select assignee_id, unassigned_at from collection_assignments order by assigned_at"
    )
    assert len(rows) == 2 and rows[0][1] is not None and rows[1][1] is None
    assert second["history"][-1]["note"] == "reassigned"
    # the first collector lost access
    assert act(env, "collector", task, "start").status_code == 403
    cancelled = act(env, "manager", task, "cancel", {"reason": "Resolved by the neighbours"})
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert (
        sql(env, "select count(*) from collection_assignments where unassigned_at is null")[0][0]
        == 0
    )
    assert (
        act(env, "manager", task, "assign", {"assignee_id": str(env.ids["collector"])}).status_code
        == 409
    )


def test_manager_can_act_for_a_collector_and_invalid_transitions_are_409(env: Env) -> None:
    task = new_task(env)
    assert act(env, "manager", task, "start").status_code == 409  # pending cannot start
    assert act(env, "manager", task, "complete", {"collected_weight_kg": "1"}).status_code == 409
    assert act(env, "manager", task, "fail", {"reason": "nothing to fail yet"}).status_code == 409
    assign(env, task)
    assert act(env, "manager", task, "start").status_code == 200  # managers may act for anyone
    reschedule = act(env, "manager", task, "reschedule", {"due_at": "2099-01-01T00:00:00Z"})
    assert reschedule.status_code == 409  # in progress cannot be rescheduled


def test_assignment_validation(env: Env) -> None:
    task = new_task(env)
    # a citizen cannot execute collection tasks; unknown / inactive users are rejected
    assert (
        act(env, "manager", task, "assign", {"assignee_id": str(env.ids["citizen"])}).status_code
        == 422
    )
    assert (
        act(env, "manager", task, "assign", {"assignee_id": str(uuid.uuid4())}).status_code == 422
    )
    sleeper = create_user(
        env.engine, email="sleeper@example.org", roles=("collector",), active=False
    )
    assert act(env, "manager", task, "assign", {"assignee_id": str(sleeper)}).status_code == 422
    assert (
        act(
            env,
            "manager",
            task,
            "assign",
            {"assignee_id": str(env.ids["collector"]), "vehicle_id": str(uuid.uuid4())},
        ).status_code
        == 422
    )
    van = env.client.post(
        FLEET,
        json={
            "registration_number": "TS 11 ZZ 0001",
            "vehicle_type": "van",
            "capacity_kg": 100,
            "status": "maintenance",
        },
        headers=env.h["manager"],
    ).json()
    blocked = act(
        env,
        "manager",
        task,
        "assign",
        {"assignee_id": str(env.ids["collector"]), "vehicle_id": van["id"]},
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "vehicle_unavailable"
    assert (
        env.client.get(f"{TASKS}/{task['id']}", headers=env.h["manager"]).json()["status"]
        == "pending"
    )


def test_vehicle_with_open_task_cannot_go_to_maintenance(env: Env) -> None:
    van = env.client.post(
        FLEET,
        json={"registration_number": "TS 22 AA 0002", "vehicle_type": "van", "capacity_kg": 100},
        headers=env.h["manager"],
    ).json()
    task = new_task(env)
    assign(env, task, vehicle_id=van["id"])
    blocked = env.client.patch(
        f"{FLEET}/{van['id']}", json={"status": "maintenance"}, headers=env.h["manager"]
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "vehicle_in_use"
    act(env, "manager", task, "cancel", {"reason": "test over"})
    freed = env.client.patch(
        f"{FLEET}/{van['id']}", json={"status": "maintenance"}, headers=env.h["manager"]
    )
    assert freed.status_code == 200


def test_events_and_completion_validation(env: Env) -> None:
    hub = facility(env)
    inactive = facility(env, code="OLD-1", status="inactive")
    task = new_task(env)
    assign(env, task)
    # events need an in-progress task
    assert act(env, "collector", task, "events", {"event_type": "arrived"}).status_code == 409
    act(env, "collector", task, "start")
    future = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=2)).isoformat()
    assert (
        act(
            env, "collector", task, "events", {"event_type": "arrived", "occurred_at": future}
        ).status_code
        == 422
    )
    assert (
        act(
            env,
            "collector",
            task,
            "events",
            {"event_type": "skipped", "facility_id": str(uuid.uuid4())},
        ).status_code
        == 422
    )
    ok = act(
        env,
        "collector",
        task,
        "events",
        {
            "event_type": "delivered_to_facility",
            "facility_id": hub["id"],
            "notes": "dropped at the gate",
        },
    )
    assert ok.status_code == 201
    for bad in (
        {"collected_weight_kg": "0"},
        {"collected_weight_kg": "-3"},
        {},
        {"collected_weight_kg": "abc"},
        {"collected_weight_kg": "1", "destination_facility_id": inactive["id"]},
        {"collected_weight_kg": "1", "destination_facility_id": str(uuid.uuid4())},
    ):
        assert act(env, "collector", task, "complete", bad).status_code == 422, bad
    assert act(env, "collector", task, "fail", {"reason": "ab"}).status_code == 422
    assert (
        env.client.get(f"{TASKS}/{task['id']}", headers=env.h["manager"]).json()["status"]
        == "in_progress"
    )


def test_listing_filters_sorting_and_my_tasks(env: Env) -> None:
    urgent = new_task(env, title="Urgent one", priority="urgent")
    low = new_task(env, title="Low one", priority="low", due_at="2099-05-01T00:00:00Z")
    normal = new_task(env, title="Normal one")
    assign(env, urgent, "collector")
    page = env.client.get(TASKS, headers=env.h["manager"]).json()
    assert page["total"] == 3
    by_priority = env.client.get(
        f"{TASKS}?sort_by=priority&order=desc", headers=env.h["manager"]
    ).json()
    assert [t["title"] for t in by_priority["items"]] == ["Urgent one", "Normal one", "Low one"]
    assert env.client.get(f"{TASKS}?status=assigned", headers=env.h["manager"]).json()["total"] == 1
    assert (
        env.client.get(f"{TASKS}?priority=low", headers=env.h["manager"]).json()["items"][0]["id"]
        == low["id"]
    )
    mine = env.client.get(f"{TASKS}?mine=true", headers=env.h["collector"]).json()
    assert [t["id"] for t in mine["items"]] == [urgent["id"]]
    assert env.client.get(f"{TASKS}?mine=true", headers=env.h["collector2"]).json()["total"] == 0
    assert (
        env.client.get(f"{TASKS}?q=normal", headers=env.h["manager"]).json()["items"][0]["id"]
        == normal["id"]
    )
    assert env.client.get(f"{TASKS}?q=%25", headers=env.h["manager"]).json()["total"] == 0
    before = env.client.get(
        f"{TASKS}?due_before=2100-01-01T00:00:00Z", headers=env.h["manager"]
    ).json()
    assert before["total"] == 1
    assert env.client.get(f"{TASKS}?status=bogus", headers=env.h["manager"]).status_code == 422
    assert env.client.get(f"{TASKS}/{uuid.uuid4()}", headers=env.h["manager"]).status_code == 404
    assert env.client.get(f"{TASKS}/not-a-uuid", headers=env.h["manager"]).status_code == 422


def test_reward_policy_can_be_disabled_and_is_idempotent(
    env: Env, make_client: ClientFactory
) -> None:
    client = make_client(reward_points_per_kg=0)
    heads = {
        n: bearer(login(client, f"{n}@example.org")["access_token"])
        for n in ("citizen", "manager", "collector")
    }
    created = client.post(
        REPORTS, json={"title": "Pile of rubble", "address_text": "x"}, headers=heads["citizen"]
    ).json()
    client.post(
        f"{REPORTS}/{created['id']}/review", json={"status": "verified"}, headers=heads["manager"]
    )
    task = client.post(
        TASKS, json={"waste_report_id": created["id"]}, headers=heads["manager"]
    ).json()
    client.post(
        f"{TASKS}/{task['id']}/assign",
        json={"assignee_id": str(env.ids["collector"])},
        headers=heads["manager"],
    )
    client.post(f"{TASKS}/{task['id']}/start", headers=heads["collector"])
    done = client.post(
        f"{TASKS}/{task['id']}/complete",
        json={"collected_weight_kg": "100"},
        headers=heads["collector"],
    )
    assert done.status_code == 200
    assert sql(env, "select count(*) from reward_ledger_entries")[0][0] == 0  # rate 0 = disabled
    # the report is still closed and the reporter is still told
    assert (
        client.get(f"{REPORTS}/{created['id']}", headers=heads["citizen"]).json()["status"]
        == "closed"
    )
