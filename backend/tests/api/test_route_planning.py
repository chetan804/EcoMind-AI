"""Route planning API: optimal ordering, validation, capacity, lifecycle, authorisation."""

from __future__ import annotations

import datetime as dt
import itertools
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.modules.route_planning import optimizer
from tests.fixtures.api import ClientFactory, bearer, create_user, login
from tests.fixtures.series import count

PLANS = "/api/v1/route-planning/plans"
TASKS = "/api/v1/collection/tasks"
FACILITIES = "/api/v1/facilities"
VEHICLES = "/api/v1/fleet/vehicles"
REPORTS = "/api/v1/waste-reports"
TODAY = dt.datetime.now(dt.UTC).date()
SPOTS = [  # scattered around Hyderabad
    (17.3850, 78.4867),
    (17.4399, 78.4983),
    (17.4065, 78.4772),
    (17.4239, 78.4738),
    (17.3616, 78.4747),
    (17.4435, 78.3772),
]


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
        ("manager", ("manager",)),
    ):
        ids[name] = create_user(db_engine, email=f"{name}@example.org", roles=roles)
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    return Env(client, db_engine, ids, heads)


def facility(env: Env, code: str, lat: float | None, lon: float | None, **extra: Any) -> str:
    body: dict[str, Any] = {"code": code, "name": f"Facility {code}", "facility_type": "depot"}
    if lat is not None:
        body.update(latitude=str(lat), longitude=str(lon))
    body.update(extra)
    response = env.client.post(FACILITIES, json=body, headers=env.h["manager"])
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def task(env: Env, spot: int | None, **extra: Any) -> str:
    body: dict[str, Any] = {"title": f"Pickup {spot}"}
    if spot is not None:
        body.update(latitude=str(SPOTS[spot][0]), longitude=str(SPOTS[spot][1]))
    body.update(extra)
    response = env.client.post(TASKS, json=body, headers=env.h["manager"])
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def create(env: Env, who: str = "manager", **body: Any) -> Any:
    return env.client.post(PLANS, json=body, headers=env.h[who])


@pytest.fixture
def world(env: Env) -> dict[str, Any]:
    depot = facility(env, "DEPOT", 17.4000, 78.4600)
    disposal = facility(env, "DUMP", 17.4700, 78.5200)
    tasks = [task(env, i) for i in range(len(SPOTS))]
    return {"depot": depot, "disposal": disposal, "tasks": tasks}


def body_for(world: dict[str, Any], **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Morning round",
        "planned_date": TODAY.isoformat(),
        "start_facility_id": world["depot"],
        "end_facility_id": world["disposal"],
        "task_ids": world["tasks"],
    }
    body.update(over)
    return body


def test_permissions(env: Env, world: dict[str, Any]) -> None:
    assert env.client.get(PLANS).status_code == 401
    assert env.client.get(PLANS, headers=env.h["citizen"]).status_code == 403
    assert create(env, "citizen", **body_for(world)).status_code == 403
    assert create(env, "collector", **body_for(world)).status_code == 403  # read-only role
    assert env.client.get(PLANS, headers=env.h["collector"]).status_code == 200


def test_plan_is_the_optimal_order_for_straight_line_distance(
    env: Env, world: dict[str, Any]
) -> None:
    response = create(env, **body_for(world))
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["status"] == "draft" and plan["optimizer"] == "route-order 1.0.0 (exact_held_karp)"
    assert "not modelled" in plan["basis"]
    assert any("No vehicle selected" in w for w in plan["warnings"])
    stops = plan["stops"]
    assert [s["sequence"] for s in stops] == list(range(1, 8))
    assert [s["kind"] for s in stops] == ["task"] * 6 + ["facility"]
    assert stops[-1]["facility_id"] == world["disposal"]
    assert sorted(s["collection_task_id"] for s in stops[:-1]) == sorted(world["tasks"])

    # total = legs + return, and equals the brute-force optimum
    legs = sum(float(s["leg_distance_km"]) for s in stops) + float(plan["return_leg_distance_km"])
    assert float(plan["total_distance_km"]) == pytest.approx(legs, abs=0.01)
    pts = [(17.4000, 78.4600), *SPOTS, (17.4700, 78.5200)]
    dist = optimizer.haversine_matrix(pts)
    best = min(
        optimizer.route_length(dist, 0, list(p), 7) for p in itertools.permutations(range(1, 7))
    )
    assert float(plan["total_distance_km"]) == pytest.approx(best / 1000, abs=0.002)


def test_plan_survives_reload_and_is_listed(env: Env, world: dict[str, Any]) -> None:
    created = create(env, **body_for(world)).json()
    fetched = env.client.get(f"{PLANS}/{created['id']}", headers=env.h["manager"]).json()
    assert fetched["stops"] == created["stops"]
    assert fetched["total_distance_km"] == created["total_distance_km"]
    page = env.client.get(
        PLANS, params={"status": "draft", "date_from": TODAY.isoformat()}, headers=env.h["manager"]
    ).json()
    assert page["total"] == 1 and page["items"][0]["id"] == created["id"]
    none = env.client.get(PLANS, params={"status": "published"}, headers=env.h["manager"]).json()
    assert none["total"] == 0
    assert env.client.get(f"{PLANS}/{uuid.uuid4()}", headers=env.h["manager"]).status_code == 404


def test_without_a_final_facility_the_route_is_a_closed_tour(
    env: Env, world: dict[str, Any]
) -> None:
    plan = create(env, **body_for(world, end_facility_id=None)).json()
    assert [s["kind"] for s in plan["stops"]] == ["task"] * 6
    assert plan["end_facility_id"] is None


def test_same_input_gives_the_same_plan(env: Env, world: dict[str, Any]) -> None:
    first = create(env, **body_for(world)).json()
    env.client.post(f"{PLANS}/{first['id']}/cancel", json={}, headers=env.h["manager"])
    second = create(env, **body_for(world)).json()
    assert [s["collection_task_id"] for s in first["stops"]] == [
        s["collection_task_id"] for s in second["stops"]
    ]
    assert first["total_distance_km"] == second["total_distance_km"]


def test_large_plans_use_the_heuristic_and_stay_valid(env: Env, world: dict[str, Any]) -> None:
    many = [task(env, i % len(SPOTS)) for i in range(14)]
    plan = create(env, **body_for(world, task_ids=many)).json()
    assert plan["optimizer"].endswith("(nn_2opt_oropt)")
    assert sorted(s["collection_task_id"] for s in plan["stops"][:-1]) == sorted(many)


@pytest.mark.parametrize("n", [41])
def test_too_many_tasks_are_rejected(env: Env, world: dict[str, Any], n: int) -> None:
    ids = [str(uuid.uuid4()) for _ in range(n)]
    assert create(env, **body_for(world, task_ids=ids)).status_code == 422


def test_input_validation(env: Env, world: dict[str, Any]) -> None:
    ok = body_for(world)
    yesterday = (TODAY - dt.timedelta(days=1)).isoformat()
    cases = {
        "past date": body_for(world, planned_date=yesterday),
        "unknown task": body_for(world, task_ids=[str(uuid.uuid4())]),
        "duplicate task": body_for(world, task_ids=[world["tasks"][0]] * 2),
        "unknown depot": body_for(world, start_facility_id=str(uuid.uuid4())),
        "no tasks": body_for(world, task_ids=[]),
        "extra field": {**ok, "unexpected": 1},
    }
    for label, body in cases.items():
        assert create(env, **body).status_code == 422, label


def test_facility_and_task_preconditions(env: Env, world: dict[str, Any]) -> None:
    no_coords = facility(env, "NOCOORD", None, None)
    assert create(env, **body_for(world, start_facility_id=no_coords)).status_code == 422
    closed = facility(env, "CLOSED", 17.41, 78.45, status="inactive")
    assert create(env, **body_for(world, end_facility_id=closed)).status_code == 422
    blind = task(env, None, address_text="Somewhere with no coordinates")
    assert create(env, **body_for(world, task_ids=[blind])).status_code == 422
    # a cancelled task cannot be planned
    cancelled = task(env, 0)
    env.client.post(
        f"{TASKS}/{cancelled}/cancel", json={"reason": "no longer needed"}, headers=env.h["manager"]
    )
    response = create(env, **body_for(world, task_ids=[cancelled]))
    assert response.status_code == 409 and response.json()["error"]["code"] == "task_not_plannable"
    assert cancelled not in response.json()["error"]["message"]  # titles, not ids


def test_a_task_is_in_at_most_one_active_plan(env: Env, world: dict[str, Any]) -> None:
    first = create(env, **body_for(world, task_ids=world["tasks"][:3])).json()
    clash = create(env, **body_for(world, task_ids=world["tasks"][2:4]))
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "task_already_planned"
    # the message names the plan (and the task by title) instead of showing internal ids
    error = clash.json()["error"]
    assert f"plan “{first['name']}”" in error["message"]
    assert world["tasks"][2] not in error["message"]
    assert error["details"][0]["task_id"] == world["tasks"][2]
    assert error["details"][0]["plan_name"] == first["name"]
    env.client.post(f"{PLANS}/{first['id']}/cancel", json={}, headers=env.h["manager"])
    assert create(env, **body_for(world, task_ids=world["tasks"][2:4])).status_code == 201


def vehicle(env: Env, registration: str, capacity: str, status_: str = "available") -> str:
    response = env.client.post(
        VEHICLES,
        json={
            "registration_number": registration,
            "vehicle_type": "van",
            "capacity_kg": capacity,
            "status": status_,
        },
        headers=env.h["manager"],
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def heavy_task(env: Env, kg: str) -> str:
    report = env.client.post(
        REPORTS,
        json={
            "title": "Big pile",
            "latitude": "17.40",
            "longitude": "78.47",
            "estimated_weight_kg": kg,
        },
        headers=env.h["citizen"],
    ).json()
    env.client.post(
        f"{REPORTS}/{report['id']}/review", json={"status": "verified"}, headers=env.h["manager"]
    )
    return task(env, 1, waste_report_id=report["id"])


def test_vehicle_rules_and_capacity(env: Env, world: dict[str, Any]) -> None:
    broken = vehicle(env, "MAINT 1", "500", "maintenance")
    r = create(env, **body_for(world, vehicle_id=broken))
    assert r.status_code == 409 and r.json()["error"]["code"] == "vehicle_unavailable"
    assert create(env, **body_for(world, vehicle_id=str(uuid.uuid4()))).status_code == 422

    small = vehicle(env, "SMALL 1", "100")
    big_pile = heavy_task(env, "250")
    over = create(env, **body_for(world, vehicle_id=small, task_ids=[big_pile]))
    assert over.status_code == 409 and over.json()["error"]["code"] == "capacity_exceeded"

    large = vehicle(env, "LARGE 1", "1000")
    ok = create(env, **body_for(world, vehicle_id=large, task_ids=[big_pile, world["tasks"][0]]))
    assert ok.status_code == 201
    assert ok.json()["vehicle_id"] == large
    assert any("1 of 2 tasks have no weight estimate" in w for w in ok.json()["warnings"])


def test_driver_must_be_an_active_collector(env: Env, world: dict[str, Any]) -> None:
    bad = create(env, **body_for(world, driver_id=str(env.ids["citizen"])))
    assert bad.status_code == 422
    assert create(env, **body_for(world, driver_id=str(uuid.uuid4()))).status_code == 422
    good = create(env, **body_for(world, driver_id=str(env.ids["collector"])))
    assert good.status_code == 201 and good.json()["driver_id"] == str(env.ids["collector"])


def test_lifecycle_and_audit(env: Env, world: dict[str, Any]) -> None:
    plan = create(env, **body_for(world)).json()
    url = f"{PLANS}/{plan['id']}"
    published = env.client.post(f"{url}/publish", json={}, headers=env.h["manager"])
    assert published.status_code == 200 and published.json()["status"] == "published"
    assert env.client.post(f"{url}/publish", json={}, headers=env.h["manager"]).status_code == 409
    cancelled = env.client.post(
        f"{url}/cancel", json={"reason": "vehicle broke down"}, headers=env.h["manager"]
    )
    assert cancelled.json()["status"] == "cancelled"
    again = env.client.post(f"{url}/publish", json={}, headers=env.h["manager"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "invalid_plan_transition"
    assert env.client.post(f"{url}/cancel", json={}, headers=env.h["collector"]).status_code == 403
    for action in ("created", "published", "cancelled"):
        assert (
            count(
                env.engine,
                "select count(*) from audit_logs where action = :a",
                a=f"route_plan.{action}",
            )
            == 1
        )
    # a plan never changes the tasks it orders
    for task_id in world["tasks"]:
        state = env.client.get(f"{TASKS}/{task_id}", headers=env.h["manager"]).json()["status"]
        assert state == "pending"
