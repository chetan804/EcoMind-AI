"""Vehicle tracking: ingestion rules, authorisation, labels, simulator isolation, map views."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.modules.tracking import service
from tests.conftest import SettingsFactory
from tests.fixtures.api import ClientFactory, bearer, create_user, login

BASE = "/api/v1/tracking"
VEHICLES = "/api/v1/fleet/vehicles"
TASKS = "/api/v1/collection/tasks"
PLANS = "/api/v1/route-planning/plans"
FACILITIES = "/api/v1/facilities"


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def iso(moment: dt.datetime) -> str:
    return moment.isoformat()


@dataclass
class Env:
    client: TestClient
    engine: Engine
    ids: dict[str, uuid.UUID]
    h: dict[str, dict[str, str]]
    vehicle: str  # assigned to collector, with a task in progress
    other_vehicle: str  # not assigned to anyone
    task_id: str
    make: ClientFactory


def make_vehicle(env_client: TestClient, head: dict[str, str], reg: str) -> str:
    response = env_client.post(
        VEHICLES,
        json={"registration_number": reg, "vehicle_type": "van", "capacity_kg": "900"},
        headers=head,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


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
        ("admin", ("administrator",)),
    ):
        ids[name] = create_user(db_engine, email=f"{name}@example.org", roles=roles)
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    vehicle = make_vehicle(client, heads["manager"], "TS 01 AA 0001")
    other = make_vehicle(client, heads["manager"], "TS 01 AA 0002")
    task = client.post(
        TASKS,
        json={"title": "Clear market", "latitude": "17.4000", "longitude": "78.4800"},
        headers=heads["manager"],
    ).json()
    assigned = client.post(
        f"{TASKS}/{task['id']}/assign",
        json={"assignee_id": str(ids["collector"]), "vehicle_id": vehicle},
        headers=heads["manager"],
    )
    assert assigned.status_code == 200, assigned.text
    started = client.post(f"{TASKS}/{task['id']}/start", json={}, headers=heads["collector"])
    assert started.status_code == 200, started.text
    return Env(client, db_engine, ids, heads, vehicle, other, task["id"], make_client)


def report(env: Env, who: str = "collector", vehicle: str | None = None, **over: Any) -> Any:
    body: dict[str, Any] = {
        "latitude": "17.401000",
        "longitude": "78.481000",
        "recorded_at": iso(now()),
        "source": "mobile_client",
    }
    body.update(over)
    return env.client.post(
        f"{BASE}/vehicles/{vehicle or env.vehicle}/locations", json=body, headers=env.h[who]
    )


def latest(env: Env, who: str = "manager", **params: Any) -> list[dict[str, Any]]:
    response = env.client.get(f"{BASE}/vehicles", params=params, headers=env.h[who])
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


# ----------------------------------------------------------------------------- authorisation
def test_authentication_and_roles(env: Env) -> None:
    some = uuid.uuid4()
    for method, url in (
        ("get", f"{BASE}/config"),
        ("get", f"{BASE}/vehicles"),
        ("get", f"{BASE}/vehicles/{some}"),
        ("get", f"{BASE}/vehicles/{some}/locations"),
        ("post", f"{BASE}/vehicles/{some}/locations"),
        ("post", f"{BASE}/simulation/vehicles/{some}/locations"),
        ("delete", f"{BASE}/simulation/vehicles/{some}/locations"),
        ("get", f"{BASE}/collections/{some}"),
        ("get", f"{BASE}/route-plans/{some}"),
    ):
        assert getattr(env.client, method)(url).status_code == 401, (method, url)
    assert env.client.get(f"{BASE}/vehicles", headers=env.h["citizen"]).status_code == 403
    assert env.client.get(f"{BASE}/vehicles", headers=env.h["operator"]).status_code == 403
    # citizens and operators cannot report; managers cannot report as a device either
    assert report(env, "citizen").status_code == 403
    assert report(env, "operator").status_code == 403
    assert report(env, "manager").status_code == 403


def test_collector_can_report_only_for_a_vehicle_assigned_to_them(env: Env) -> None:
    assert report(env).status_code == 201
    # another collector with no assignment
    denied = report(env, "collector2")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "not_assigned_to_vehicle"
    # the owner of a different vehicle
    assert report(env, vehicle=env.other_vehicle).status_code == 403
    # an unknown vehicle is a 404
    assert report(env, vehicle=str(uuid.uuid4())).status_code == 404


def test_assignment_ending_stops_reporting(env: Env) -> None:
    assert report(env).status_code == 201
    done = env.client.post(
        f"{TASKS}/{env.task_id}/complete",
        json={"collected_weight_kg": "10"},
        headers=env.h["collector"],
    )
    assert done.status_code == 200, done.text
    assert report(env, recorded_at=iso(now())).status_code == 403


def test_simulator_source_cannot_be_posted_to_the_real_endpoint(env: Env) -> None:
    assert report(env, source="simulator").status_code == 422
    assert report(env, "manager", source="simulator").status_code == 422


def test_import_needs_manager_and_must_be_historical(env: Env) -> None:
    old = now() - dt.timedelta(days=2)
    assert report(env, "collector", source="imported", recorded_at=iso(old)).status_code == 403
    ok = report(env, "manager", vehicle=env.other_vehicle, source="imported", recorded_at=iso(old))
    assert ok.status_code == 201, ok.text
    recent = report(
        env, "manager", vehicle=env.other_vehicle, source="imported", recorded_at=iso(now())
    )
    assert recent.status_code == 422
    rows = (
        env.engine.connect()
        .execute(text("SELECT action FROM audit_logs WHERE action = 'tracking.location_imported'"))
        .all()
    )
    assert len(rows) == 1


# ----------------------------------------------------------------------------- validation
@pytest.mark.parametrize(
    "override",
    [
        {"latitude": "91"},
        {"latitude": "-90.5"},
        {"longitude": "180.1"},
        {"latitude": "abc"},
        {"latitude": "17.1234567"},  # more than 6 decimals
        {"latitude": "0", "longitude": "0"},  # null island placeholder
        {"accuracy_m": "-1"},
        {"speed_kph": "301"},
        {"speed_kph": "-2"},
        {"heading_deg": "360"},
        {"heading_deg": "-1"},
        {"sequence": -1},
        {"source": "gps"},
        {"recorded_at": "2026-01-01T00:00:00"},  # naive timestamp
        {"unexpected": 1},
    ],
)
def test_invalid_events_are_rejected(env: Env, override: dict[str, Any]) -> None:
    response = report(env, **override)
    assert response.status_code == 422, (override, response.text)
    assert latest(env)[0]["status"] == "unavailable"


def test_future_and_too_old_timestamps(env: Env) -> None:
    future = report(env, recorded_at=iso(now() + dt.timedelta(minutes=10)))
    assert future.status_code == 422 and "future" in future.json()["error"]["message"]
    old = report(env, recorded_at=iso(now() - dt.timedelta(hours=7)))
    assert old.status_code == 422 and "older" in old.json()["error"]["message"]
    skewed = report(env, recorded_at=iso(now() + dt.timedelta(seconds=30)))
    assert skewed.status_code == 201  # inside the allowed clock skew


def test_timestamps_with_offsets_are_normalised_to_utc(env: Env) -> None:
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    moment = now().astimezone(ist) - dt.timedelta(seconds=5)
    response = report(env, recorded_at=moment.isoformat())
    assert response.status_code == 201, response.text
    stored = dt.datetime.fromisoformat(response.json()["event"]["recorded_at"])
    assert stored == moment
    assert latest(env)[0]["status"] == "live"


def test_task_and_plan_links_are_validated(env: Env) -> None:
    foreign = env.client.post(
        TASKS,
        json={"title": "Elsewhere", "latitude": "17.5", "longitude": "78.5"},
        headers=env.h["manager"],
    ).json()["id"]
    assert report(env, collection_task_id=foreign).status_code == 422
    assert report(env, route_plan_id=str(uuid.uuid4())).status_code == 422


# ----------------------------------------------------------------------------- ingestion semantics
def test_event_is_linked_to_the_single_task_in_progress(env: Env) -> None:
    body = report(env).json()
    assert body["event"]["collection_task_id"] == env.task_id
    explicit = report(env, collection_task_id=env.task_id, recorded_at=iso(now())).json()
    assert explicit["event"]["collection_task_id"] == env.task_id


def test_duplicates_are_idempotent(env: Env) -> None:
    moment = iso(now() - dt.timedelta(seconds=3))
    first = report(env, recorded_at=moment, sequence=7)
    assert first.status_code == 201 and first.json()["duplicate"] is False
    same_time = report(env, recorded_at=moment, latitude="17.5")
    assert same_time.status_code == 200 and same_time.json()["duplicate"] is True
    assert same_time.json()["event"]["id"] == first.json()["event"]["id"]
    same_sequence = report(env, recorded_at=iso(now() - dt.timedelta(seconds=2)), sequence=7)
    assert same_sequence.status_code == 200 and same_sequence.json()["duplicate"] is True
    count = (
        env.engine.connect().execute(text("SELECT count(*) FROM vehicle_location_events")).scalar()
    )
    assert count == 1


def test_out_of_order_events_are_stored_but_never_become_the_latest(env: Env) -> None:
    newer = now() - dt.timedelta(seconds=5)
    older = now() - dt.timedelta(seconds=60)
    assert (
        report(env, recorded_at=iso(newer), latitude="17.410000").json()["event"]["quality"]
        == "accepted"
    )
    late = report(env, recorded_at=iso(older), latitude="17.300000")
    assert late.status_code == 201 and late.json()["event"]["quality"] == "out_of_order"
    position = latest(env)[0]["position"]
    assert position["latitude"] == "17.410000"
    history = env.client.get(
        f"{BASE}/vehicles/{env.vehicle}/locations", headers=env.h["manager"]
    ).json()
    assert history["total"] == 2
    assert [e["latitude"] for e in history["items"]] == ["17.410000", "17.300000"]  # newest first


def test_rate_limit_per_vehicle(make_client: ClientFactory, env: Env) -> None:
    limited = make_client(tracking_max_events_per_minute=3)
    head = bearer(login(limited, "collector@example.org")["access_token"])
    codes = []
    for second in range(5):
        stamp = now() - dt.timedelta(seconds=second + 1)
        response = limited.post(
            f"{BASE}/vehicles/{env.vehicle}/locations",
            json={
                "latitude": "17.4",
                "longitude": "78.48",
                "recorded_at": iso(stamp),
                "source": "gps_device",
            },
            headers=head,
        )
        codes.append(response.status_code)
    assert codes == [201, 201, 201, 429, 429]
    assert response.headers["retry-after"] == "10"


def test_retired_vehicle_is_rejected(env: Env) -> None:
    env.client.patch(
        f"{VEHICLES}/{env.other_vehicle}", json={"status": "retired"}, headers=env.h["manager"]
    )
    old = iso(now() - dt.timedelta(days=1))
    assert (
        report(
            env, "manager", vehicle=env.other_vehicle, source="imported", recorded_at=old
        ).status_code
        == 409
    )


def test_events_are_immutable_in_the_database(env: Env) -> None:
    report(env)
    with pytest.raises(DBAPIError, match="append-only"), env.engine.begin() as conn:
        conn.execute(text("UPDATE vehicle_location_events SET latitude = 10"))


# ----------------------------------------------------------------------------- labels
def test_status_labels_follow_source_and_age(env: Env) -> None:
    assert latest(env)[0]["status"] == "unavailable"
    assert latest(env)[0]["position"] is None
    report(env, recorded_at=iso(now() - dt.timedelta(seconds=10)))
    row = next(r for r in latest(env) if r["vehicle_id"] == env.vehicle)
    assert row["status"] == "live" and row["simulated"] is False
    assert 10 <= row["position"]["age_seconds"] < 60
    assert row["position"]["source"] == "mobile_client"
    # age thresholds: shift the stored timestamp instead of waiting
    for seconds, label in ((300, "delayed"), (3600, "stale")):
        with env.engine.begin() as conn:
            conn.execute(text("ALTER TABLE vehicle_location_events DISABLE TRIGGER USER"))
            conn.execute(
                text("UPDATE vehicle_location_events SET recorded_at = :t"),
                {"t": now() - dt.timedelta(seconds=seconds)},
            )
            conn.execute(text("ALTER TABLE vehicle_location_events ENABLE TRIGGER USER"))
        row = next(r for r in latest(env) if r["vehicle_id"] == env.vehicle)
        assert row["status"] == label, (seconds, row["status"])
    # an imported track is always historical, however fresh its timestamp looks
    report(
        env,
        "manager",
        vehicle=env.other_vehicle,
        source="imported",
        recorded_at=iso(now() - dt.timedelta(days=1)),
    )
    other = next(r for r in latest(env) if r["vehicle_id"] == env.other_vehicle)
    assert other["status"] == "historical"


def test_a_stationary_registered_vehicle_is_never_reported_as_live(env: Env) -> None:
    rows = latest(env)
    assert {r["status"] for r in rows} == {"unavailable"}
    assert all(r["position"] is None for r in rows)


def test_collector_sees_only_assigned_vehicles(env: Env) -> None:
    report(env)
    rows = latest(env, "collector")
    assert [r["vehicle_id"] for r in rows] == [env.vehicle]
    assert len(latest(env, "manager")) == 2
    assert len(latest(env, "collector2")) == 0
    denied = env.client.get(f"{BASE}/vehicles/{env.other_vehicle}", headers=env.h["collector"])
    assert denied.status_code == 404
    denied_history = env.client.get(
        f"{BASE}/vehicles/{env.other_vehicle}/locations", headers=env.h["collector"]
    )
    assert denied_history.status_code == 404
    assert (
        env.client.get(f"{BASE}/vehicles/{env.vehicle}", headers=env.h["collector"]).status_code
        == 200
    )


# ----------------------------------------------------------------------------- simulator
def simulate(env: Env, vehicle: str | None = None, who: str = "manager", **over: Any) -> Any:
    body: dict[str, Any] = {"latitude": "17.42", "longitude": "78.46"}
    body.update(over)
    return env.client.post(
        f"{BASE}/simulation/vehicles/{vehicle or env.vehicle}/locations",
        json=body,
        headers=env.h[who],
    )


def test_simulator_permissions(env: Env) -> None:
    assert simulate(env, who="collector").status_code == 403
    assert simulate(env, who="operator").status_code == 403
    assert simulate(env, who="manager").status_code == 201


def test_simulated_positions_are_separate_labelled_and_never_replace_real_ones(env: Env) -> None:
    report(env, latitude="17.401000", recorded_at=iso(now() - dt.timedelta(seconds=5)))
    sim = simulate(env, latitude="17.9", recorded_at=iso(now()))
    assert sim.status_code == 201
    assert sim.json()["event"]["source"] == "simulator"
    assert sim.json()["event"]["collection_task_id"] is None  # never attached to a real task
    # default: simulator data is hidden
    default = [r for r in latest(env) if r["vehicle_id"] == env.vehicle]
    assert [r["simulated"] for r in default] == [False]
    assert default[0]["position"]["latitude"] == "17.401000"
    both = [r for r in latest(env, include_simulated="true") if r["vehicle_id"] == env.vehicle]
    assert [(r["simulated"], r["status"]) for r in both] == [(False, "live"), (True, "simulated")]
    # history excludes simulator unless asked
    url = f"{BASE}/vehicles/{env.vehicle}/locations"
    assert env.client.get(url, headers=env.h["manager"]).json()["total"] == 1
    assert (
        env.client.get(url, params={"include_simulated": "true"}, headers=env.h["manager"]).json()[
            "total"
        ]
        == 2
    )
    assert (
        env.client.get(url, params={"source": "simulator"}, headers=env.h["manager"]).json()[
            "total"
        ]
        == 1
    )


def test_simulated_only_vehicle_still_shows_real_as_unavailable(env: Env) -> None:
    simulate(env, vehicle=env.other_vehicle)
    rows = [
        r for r in latest(env, include_simulated="true") if r["vehicle_id"] == env.other_vehicle
    ]
    assert [(r["simulated"], r["status"]) for r in rows] == [
        (False, "unavailable"),
        (True, "simulated"),
    ]


def test_reset_removes_only_simulator_events(env: Env) -> None:
    report(env)
    simulate(env)
    simulate(env, recorded_at=iso(now() - dt.timedelta(seconds=1)))
    other = simulate(env, vehicle=env.other_vehicle)
    assert other.status_code == 201
    reset = env.client.delete(
        f"{BASE}/simulation/vehicles/{env.vehicle}/locations", headers=env.h["manager"]
    )
    assert reset.status_code == 200 and reset.json() == {"removed": 2}
    sources = [
        r[0]
        for r in env.engine.connect().execute(
            text("SELECT source FROM vehicle_location_events ORDER BY source")
        )
    ]
    assert sources == [
        "mobile_client",
        "simulator",
    ]  # real event kept, other vehicle's simulator kept
    assert (
        env.client.delete(
            f"{BASE}/simulation/vehicles/{env.vehicle}/locations", headers=env.h["collector"]
        ).status_code
        == 403
    )


def test_simulator_disabled_in_production_like_settings(
    make_client: ClientFactory, env: Env
) -> None:
    off = make_client(tracking_simulator_enabled=False)
    head = bearer(login(off, "manager@example.org")["access_token"])
    url = f"{BASE}/simulation/vehicles/{env.vehicle}/locations"
    response = off.post(url, json={"latitude": "17.4", "longitude": "78.4"}, headers=head)
    assert response.status_code == 404 and response.json()["error"]["code"] == "simulator_disabled"
    assert off.delete(url, headers=head).status_code == 404
    config = off.get(f"{BASE}/config", headers=head).json()
    assert config["simulator_enabled"] is False


def test_config_reports_policy_without_secrets(env: Env, make_client: ClientFactory) -> None:
    config = env.client.get(f"{BASE}/config", headers=env.h["collector"]).json()
    assert config["live_within_seconds"] == 120 and config["stale_after_seconds"] == 900
    assert config["road_routing_configured"] is False
    keyed = make_client(google_maps_server_api_key="server-key-value-1234567890")
    head = bearer(login(keyed, "manager@example.org")["access_token"])
    body = keyed.get(f"{BASE}/config", headers=head)
    assert body.json()["road_routing_configured"] is True
    assert "server-key-value" not in body.text


# ----------------------------------------------------------------------------- retention
def test_retention_purge_removes_only_expired_rows(
    env: Env, make_settings: SettingsFactory
) -> None:
    report(env, recorded_at=iso(now() - dt.timedelta(seconds=5)))
    old = iso(now() - dt.timedelta(days=100))
    imported = report(env, "manager", vehicle=env.other_vehicle, source="imported", recorded_at=old)
    assert imported.status_code == 201
    with Session(env.engine) as db:
        assert service.purge_expired(db, make_settings(tracking_retention_days=90)) == 1
    remaining = (
        env.engine.connect().execute(text("SELECT source FROM vehicle_location_events")).all()
    )
    assert [r[0] for r in remaining] == ["mobile_client"]


# ----------------------------------------------------------------------------- map views
def test_collection_tracking_returns_only_linked_positions(env: Env) -> None:
    for i, lat in enumerate(("17.4010", "17.4020", "17.4030")):
        report(env, latitude=lat, recorded_at=iso(now() - dt.timedelta(seconds=30 - i * 5)))
    track = env.client.get(f"{BASE}/collections/{env.task_id}", headers=env.h["collector"])
    assert track.status_code == 200, track.text
    body = track.json()
    assert [p["latitude"] for p in body["path"]] == ["17.401000", "17.402000", "17.403000"]
    assert body["vehicle"]["status"] == "live" and body["vehicle_id"] == env.vehicle
    assert body["latitude"] == "17.400000"
    # managers can see it, others cannot
    assert (
        env.client.get(f"{BASE}/collections/{env.task_id}", headers=env.h["manager"]).status_code
        == 200
    )
    assert (
        env.client.get(f"{BASE}/collections/{env.task_id}", headers=env.h["collector2"]).status_code
        == 403
    )
    assert (
        env.client.get(f"{BASE}/collections/{env.task_id}", headers=env.h["operator"]).status_code
        == 403
    )
    assert (
        env.client.get(f"{BASE}/collections/{uuid.uuid4()}", headers=env.h["manager"]).status_code
        == 404
    )
    # simulator positions never appear in a collection's path
    simulate(env, recorded_at=iso(now()))
    again = env.client.get(f"{BASE}/collections/{env.task_id}", headers=env.h["manager"]).json()
    assert len(again["path"]) == 3


def make_plan(env: Env) -> tuple[str, list[str]]:
    depot = env.client.post(
        FACILITIES,
        json={
            "code": "DEP",
            "name": "Depot",
            "facility_type": "depot",
            "latitude": "17.40",
            "longitude": "78.46",
        },
        headers=env.h["manager"],
    ).json()["id"]
    tasks = []
    for i, (lat, lon) in enumerate((("17.41", "78.47"), ("17.43", "78.49"))):
        tasks.append(
            env.client.post(
                TASKS,
                json={"title": f"Stop {i}", "latitude": lat, "longitude": lon},
                headers=env.h["manager"],
            ).json()["id"]
        )
    plan = env.client.post(
        PLANS,
        json={
            "name": "Round",
            "planned_date": now().date().isoformat(),
            "start_facility_id": depot,
            "task_ids": tasks,
            "vehicle_id": env.vehicle,
        },
        headers=env.h["manager"],
    )
    assert plan.status_code == 201, plan.text
    return plan.json()["id"], tasks


def test_route_tracking_progress_comes_from_task_state_and_paths_from_events(env: Env) -> None:
    plan_id, _tasks = make_plan(env)
    url = f"{BASE}/route-plans/{plan_id}"
    before = env.client.get(url, headers=env.h["manager"]).json()
    assert before["total_task_stops"] == 2 and before["completed_task_stops"] == 0
    assert before["vehicle"]["status"] == "unavailable" and before["path"] == []
    report(env, route_plan_id=plan_id, recorded_at=iso(now() - dt.timedelta(seconds=4)))
    # complete one stop through the real workflow
    first = before["stops"][0]["task_id"]
    for verb, who, body in (
        (
            "assign",
            "manager",
            {"assignee_id": str(env.ids["collector"]), "vehicle_id": env.vehicle},
        ),
        ("start", "collector", {}),
        ("complete", "collector", {"collected_weight_kg": "5"}),
    ):
        done = env.client.post(f"{TASKS}/{first}/{verb}", json=body, headers=env.h[who])
        assert done.status_code == 200, done.text
    after = env.client.get(url, headers=env.h["manager"]).json()
    assert after["completed_task_stops"] == 1 and after["total_task_stops"] == 2
    assert [s["completed"] for s in after["stops"] if s["kind"] == "task"] == [True, False]
    assert len(after["path"]) == 1 and after["path_simulated"] is False
    assert after["vehicle"]["status"] == "live"
    # simulated overlay only on request, and never counted as progress
    simulate(env, route_plan_id=plan_id, recorded_at=iso(now()))
    plain = env.client.get(url, headers=env.h["manager"]).json()
    assert plain["path_simulated"] is False and len(plain["path"]) == 1
    sim = env.client.get(url, params={"include_simulated": "true"}, headers=env.h["manager"]).json()
    assert sim["completed_task_stops"] == 1
    assert (
        env.client.get(f"{BASE}/route-plans/{uuid.uuid4()}", headers=env.h["manager"]).status_code
        == 404
    )


def test_route_tracking_hides_vehicle_from_unrelated_collector(env: Env) -> None:
    plan_id, _ = make_plan(env)
    report(env, route_plan_id=plan_id)
    mine = env.client.get(f"{BASE}/route-plans/{plan_id}", headers=env.h["collector"]).json()
    assert mine["vehicle"] is not None
    theirs = env.client.get(f"{BASE}/route-plans/{plan_id}", headers=env.h["collector2"]).json()
    assert theirs["vehicle"] is None and theirs["path"] == []
    assert len(theirs["stops"]) == 2  # the plan itself is visible to every routes:read role
