"""``GET /route-planning/plans/{id}/road-route`` with the routing provider replaced by a fake."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.integrations.mapping.base import LatLng, RoadRoute, RoadRouteUnavailable
from app.modules.route_planning.router import get_road_route_provider
from tests.fixtures.api import ClientFactory, bearer, create_user, login

PLANS = "/api/v1/route-planning/plans"


class FakeProvider:
    name = "fake"

    def __init__(self, outcome: RoadRoute | RoadRouteUnavailable) -> None:
        self.outcome = outcome
        self.calls: list[Sequence[LatLng]] = []

    def route(self, points: Sequence[LatLng]) -> RoadRoute | RoadRouteUnavailable:
        self.calls.append(list(points))
        return self.outcome


@pytest.fixture
def setup(
    make_client: ClientFactory, db_engine: Engine
) -> tuple[TestClient, dict[str, dict[str, str]], str]:
    client = make_client()
    heads = {}
    for name, roles in (("manager", ("manager",)), ("citizen", ("citizen",))):
        create_user(db_engine, email=f"{name}@example.org", roles=roles)
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    depot = client.post(
        "/api/v1/facilities",
        json={
            "code": "D1",
            "name": "Depot",
            "facility_type": "depot",
            "latitude": "17.40",
            "longitude": "78.46",
        },
        headers=heads["manager"],
    ).json()["id"]
    tasks = [
        client.post(
            "/api/v1/collection/tasks",
            json={"title": f"Pickup {i}", "latitude": lat, "longitude": "78.48"},
            headers=heads["manager"],
        ).json()["id"]
        for i, lat in enumerate(("17.41", "17.43"))
    ]
    plan = client.post(
        PLANS,
        json={
            "name": "Round",
            "planned_date": dt.datetime.now(dt.UTC).date().isoformat(),
            "start_facility_id": depot,
            "task_ids": tasks,
        },
        headers=heads["manager"],
    )
    assert plan.status_code == 201, plan.text
    return client, heads, str(plan.json()["id"])


def override(client: TestClient, provider: FakeProvider) -> None:
    client.app.dependency_overrides[get_road_route_provider] = lambda: provider  # type: ignore[attr-defined]


def test_without_a_key_the_answer_is_explicitly_unavailable(
    setup: tuple[TestClient, dict[str, dict[str, str]], str],
) -> None:
    client, heads, plan_id = setup
    body = client.get(f"{PLANS}/{plan_id}/road-route", headers=heads["manager"]).json()
    assert body["available"] is False and body["reason"] == "not_configured"
    assert body["encoded_polylines"] == [] and body["distance_m"] is None


def test_route_goes_depot_to_depot_through_every_stop_in_plan_order(
    setup: tuple[TestClient, dict[str, dict[str, str]], str],
) -> None:
    client, heads, plan_id = setup
    plan = client.get(f"{PLANS}/{plan_id}", headers=heads["manager"]).json()
    fake = FakeProvider(
        RoadRoute("fake", ("abc",), 4321, 777, traffic_aware=False, request_count=1)
    )
    override(client, fake)
    body = client.get(f"{PLANS}/{plan_id}/road-route", headers=heads["manager"]).json()
    assert body["available"] is True and body["provider"] == "fake"
    assert body["encoded_polylines"] == ["abc"] and body["distance_m"] == 4321
    assert body["duration_s"] == 777 and body["traffic_aware"] is False
    assert "without live traffic" in body["basis"]
    (points,) = fake.calls
    expected = [
        (17.40, 78.46),
        *[(float(s["latitude"]), float(s["longitude"])) for s in plan["stops"]],
        (17.40, 78.46),
    ]
    assert [(p.latitude, p.longitude) for p in points] == expected


@pytest.mark.parametrize("reason", ["quota_exceeded", "timeout", "access_denied", "network_error"])
def test_provider_failure_is_reported_not_raised(
    setup: tuple[TestClient, dict[str, dict[str, str]], str], reason: str
) -> None:
    client, heads, plan_id = setup
    override(client, FakeProvider(RoadRouteUnavailable(reason=reason, provider="fake")))  # type: ignore[arg-type]
    response = client.get(f"{PLANS}/{plan_id}/road-route", headers=heads["manager"])
    assert response.status_code == 200
    assert response.json()["available"] is False and response.json()["reason"] == reason


def test_access_control_and_missing_plan(
    setup: tuple[TestClient, dict[str, dict[str, str]], str],
) -> None:
    client, heads, plan_id = setup
    assert client.get(f"{PLANS}/{plan_id}/road-route").status_code == 401
    assert client.get(f"{PLANS}/{plan_id}/road-route", headers=heads["citizen"]).status_code == 403
    missing = client.get(f"{PLANS}/{uuid.uuid4()}/road-route", headers=heads["manager"])
    assert missing.status_code == 404


def test_plan_detail_exposes_the_depot_point(
    setup: tuple[TestClient, dict[str, dict[str, str]], str],
) -> None:
    client, heads, plan_id = setup
    plan = client.get(f"{PLANS}/{plan_id}", headers=heads["manager"]).json()
    assert float(plan["start_latitude"]) == 17.40 and float(plan["start_longitude"]) == 78.46
