"""Fleet vehicles: authorisation, validation, uniqueness and the in-use guard."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.fixtures.api import ClientFactory, bearer, create_user, login

URL = "/api/v1/fleet/vehicles"


@dataclass
class Env:
    client: TestClient
    engine: Engine
    citizen: dict[str, str]
    collector: dict[str, str]
    manager: dict[str, str]


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    client = make_client()
    heads = {}
    for name, roles in (
        ("citizen", ("citizen",)),
        ("collector", ("collector",)),
        ("manager", ("manager",)),
    ):
        create_user(db_engine, email=f"{name}@example.org", roles=roles)
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    return Env(client, db_engine, heads["citizen"], heads["collector"], heads["manager"])


def make(env: Env, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "registration_number": "ts 09 ab 1234",
        "vehicle_type": "compactor_truck",
        "capacity_kg": "3500",
    }
    body.update(overrides)
    response = env.client.post(URL, json=body, headers=env.manager)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def test_authentication_and_authorization(env: Env) -> None:
    some = uuid.uuid4()
    assert env.client.get(URL).status_code == 401
    assert env.client.post(URL, json={}).status_code == 401
    assert env.client.patch(f"{URL}/{some}", json={}).status_code == 401
    # citizens have no fleet permission at all; collectors can read; only managers write
    assert env.client.get(URL, headers=env.citizen).status_code == 403
    assert env.client.get(URL, headers=env.collector).status_code == 200
    body = {"registration_number": "AB 123", "vehicle_type": "van", "capacity_kg": 100}
    assert env.client.post(URL, json=body, headers=env.collector).status_code == 403
    created = make(env)
    resp = env.client.patch(
        f"{URL}/{created['id']}", json={"status": "retired"}, headers=env.collector
    )
    assert resp.status_code == 403


def test_create_normalises_registration_and_rejects_duplicates(env: Env) -> None:
    created = make(env)
    assert created["registration_number"] == "TS 09 AB 1234"
    assert created["status"] == "available"
    assert created["active_task_count"] == 0
    duplicate = env.client.post(
        URL,
        json={"registration_number": "TS  09 ab 1234", "vehicle_type": "van", "capacity_kg": 10},
        headers=env.manager,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "vehicle_registration_taken"


@pytest.mark.parametrize(
    "overrides",
    [
        {"registration_number": "x"},
        {"registration_number": "bad!plate"},
        {"capacity_kg": 0},
        {"capacity_kg": -5},
        {"vehicle_type": "spaceship"},
        {"status": "flying"},
        {"unknown_field": 1},
        {"home_facility_id": str(uuid.uuid4())},
    ],
)
def test_create_validation(env: Env, overrides: dict[str, Any]) -> None:
    body: dict[str, Any] = {
        "registration_number": "TS 09 AB 1234",
        "vehicle_type": "van",
        "capacity_kg": 100,
    }
    body.update(overrides)
    assert env.client.post(URL, json=body, headers=env.manager).status_code == 422


def test_update_is_partial_audited_and_registration_is_immutable(env: Env) -> None:
    created = make(env)
    vid = created["id"]
    resp = env.client.patch(
        f"{URL}/{vid}", json={"capacity_kg": "4000", "status": "maintenance"}, headers=env.manager
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["capacity_kg"] == "4000.000"
    assert resp.json()["status"] == "maintenance"
    assert resp.json()["vehicle_type"] == "compactor_truck"  # untouched
    immutable = env.client.patch(
        f"{URL}/{vid}", json={"registration_number": "OTHER 1"}, headers=env.manager
    )
    assert immutable.status_code == 422
    assert (
        env.client.patch(f"{URL}/{vid}", json={"status": None}, headers=env.manager).status_code
        == 422
    )
    assert (
        env.client.patch(f"{URL}/{uuid.uuid4()}", json={}, headers=env.manager).status_code == 404
    )
    # a no-op patch is accepted and writes nothing
    noop = env.client.patch(f"{URL}/{vid}", json={"status": "maintenance"}, headers=env.manager)
    assert noop.status_code == 200


def test_list_filters_search_and_pagination(env: Env) -> None:
    make(env, registration_number="AAA 111", vehicle_type="van", capacity_kg=500)
    make(env, registration_number="BBB 222", vehicle_type="tipper_truck", capacity_kg=9000)
    make(env, registration_number="CCC 333", vehicle_type="van", capacity_kg=700, status="retired")
    listing = env.client.get(URL, headers=env.manager).json()
    assert listing["total"] == 3
    assert [v["registration_number"] for v in listing["items"]] == ["AAA 111", "BBB 222", "CCC 333"]
    vans = env.client.get(f"{URL}?vehicle_type=van", headers=env.manager).json()
    assert vans["total"] == 2
    retired = env.client.get(f"{URL}?status=retired", headers=env.manager).json()
    assert [v["registration_number"] for v in retired["items"]] == ["CCC 333"]
    found = env.client.get(f"{URL}?q=bbb", headers=env.manager).json()
    assert found["total"] == 1
    # LIKE wildcards in the search term are data, not patterns
    assert env.client.get(f"{URL}?q=%25", headers=env.manager).json()["total"] == 0
    biggest = env.client.get(
        f"{URL}?sort_by=capacity_kg&order=desc&page_size=1", headers=env.manager
    )
    assert biggest.json()["items"][0]["registration_number"] == "BBB 222"
    assert env.client.get(f"{URL}?page_size=101", headers=env.manager).status_code == 422
