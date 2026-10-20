"""Zones: named service areas that facilities can belong to."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.fixtures.api import ClientFactory, bearer, create_user, login

ZONES = "/api/v1/zones"
FACILITIES = "/api/v1/facilities"


@dataclass
class Env:
    client: TestClient
    engine: Engine
    citizen: dict[str, str]
    manager: dict[str, str]


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    client = make_client()
    heads = {}
    for name, roles in (("citizen", ("citizen",)), ("manager", ("manager",))):
        create_user(db_engine, email=f"{name}@example.org", roles=roles)
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    return Env(client, db_engine, heads["citizen"], heads["manager"])


def zone(env: Env, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"code": "Z-1", "name": "Zone 1 - Commercial", "zone_type": "commercial"}
    body.update(overrides)
    response = env.client.post(ZONES, json=body, headers=env.manager)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def facility(env: Env, code: str, **extra: Any) -> dict[str, Any]:
    body = {"code": code, "name": f"Facility {code}", "facility_type": "depot", **extra}
    response = env.client.post(FACILITIES, json=body, headers=env.manager)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def test_authentication_and_authorization(env: Env) -> None:
    some = uuid.uuid4()
    assert env.client.get(ZONES).status_code == 401
    assert env.client.post(ZONES, json={}).status_code == 401
    assert env.client.get(f"{ZONES}/{some}").status_code == 401
    # any signed-in role reads; only managers change
    assert env.client.get(ZONES, headers=env.citizen).status_code == 200
    body = {"code": "Z-9", "name": "Nope", "zone_type": "other"}
    assert env.client.post(ZONES, json=body, headers=env.citizen).status_code == 403
    created = zone(env)
    patch = env.client.patch(f"{ZONES}/{created['id']}", json={"name": "X1"}, headers=env.citizen)
    assert patch.status_code == 403


def test_create_normalises_code_and_audits(env: Env) -> None:
    created = zone(env, code=" z-2 ", name="  North  ", description="  Dense retail  ")
    assert created["code"] == "Z-2" and created["name"] == "North"
    assert created["description"] == "Dense retail"
    assert created["is_active"] is True and created["facility_count"] == 0
    with env.engine.connect() as conn:
        entry = conn.execute(
            text("SELECT action, entity_type FROM audit_logs WHERE entity_id = :id"),
            {"id": created["id"]},
        ).one()
    assert tuple(entry) == ("zone.created", "zone")


def test_duplicate_code_is_a_conflict_regardless_of_case(env: Env) -> None:
    zone(env, code="Z-1")
    response = env.client.post(
        ZONES, json={"code": "z-1", "name": "Again", "zone_type": "other"}, headers=env.manager
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "zone_code_taken"


@pytest.mark.parametrize(
    "body",
    [
        {"code": "Z-1", "name": "A", "zone_type": "commercial"},  # name too short
        {"code": "!", "name": "Valid name", "zone_type": "commercial"},
        {"code": "Z-1", "name": "Valid name", "zone_type": "swamp"},
        {"code": "Z-1", "name": "Valid name", "zone_type": "commercial", "colour": "red"},
        {"name": "Valid name", "zone_type": "commercial"},
    ],
)
def test_invalid_create_bodies_are_rejected(env: Env, body: dict[str, Any]) -> None:
    assert env.client.post(ZONES, json=body, headers=env.manager).status_code == 422


def test_patch_changes_only_sent_fields_and_cannot_change_code(env: Env) -> None:
    created = zone(env)
    url = f"{ZONES}/{created['id']}"
    changed = env.client.patch(url, json={"zone_type": "mixed_use"}, headers=env.manager).json()
    assert changed["zone_type"] == "mixed_use" and changed["name"] == created["name"]
    assert env.client.patch(url, json={"code": "Z-2"}, headers=env.manager).status_code == 422
    assert env.client.patch(url, json={"name": None}, headers=env.manager).status_code == 422
    cleared = env.client.patch(url, json={"description": None}, headers=env.manager)
    assert cleared.status_code == 200 and cleared.json()["description"] is None
    assert (
        env.client.patch(f"{ZONES}/{uuid.uuid4()}", json={}, headers=env.manager).status_code == 404
    )


def test_facilities_can_join_a_zone_and_are_counted(env: Env) -> None:
    z = zone(env)
    first = facility(env, "FAC-1", zone_id=z["id"])
    facility(env, "FAC-2", zone_id=z["id"])
    facility(env, "FAC-3")
    assert first["zone_id"] == z["id"]
    assert env.client.get(f"{ZONES}/{z['id']}", headers=env.citizen).json()["facility_count"] == 2
    in_zone = env.client.get(FACILITIES, params={"zone_id": z["id"]}, headers=env.manager).json()
    assert {f["code"] for f in in_zone["items"]} == {"FAC-1", "FAC-2"}
    loose = env.client.get(FACILITIES, params={"unzoned": "true"}, headers=env.manager).json()
    assert {f["code"] for f in loose["items"]} == {"FAC-3"}


def test_a_facility_cannot_join_an_unknown_or_inactive_zone(env: Env) -> None:
    z = zone(env)
    body = {"code": "FAC-9", "name": "Facility", "facility_type": "depot"}
    unknown = env.client.post(
        FACILITIES, json={**body, "zone_id": str(uuid.uuid4())}, headers=env.manager
    )
    assert unknown.status_code == 422
    env.client.patch(f"{ZONES}/{z['id']}", json={"is_active": False}, headers=env.manager)
    inactive = env.client.post(FACILITIES, json={**body, "zone_id": z["id"]}, headers=env.manager)
    assert inactive.status_code == 422
    loose = facility(env, "FAC-8")
    moved = env.client.patch(
        f"{FACILITIES}/{loose['id']}", json={"zone_id": z["id"]}, headers=env.manager
    )
    assert moved.status_code == 422


def test_leaving_or_keeping_a_retired_zone_is_allowed(env: Env) -> None:
    z = zone(env)
    member = facility(env, "FAC-1", zone_id=z["id"])
    env.client.patch(f"{ZONES}/{z['id']}", json={"is_active": False}, headers=env.manager)
    url = f"{FACILITIES}/{member['id']}"
    kept = env.client.patch(url, json={"zone_id": z["id"], "city": "Pune"}, headers=env.manager)
    assert kept.status_code == 200 and kept.json()["zone_id"] == z["id"]
    left = env.client.patch(url, json={"zone_id": None}, headers=env.manager)
    assert left.status_code == 200 and left.json()["zone_id"] is None
    assert env.client.get(f"{ZONES}/{z['id']}", headers=env.manager).json()["facility_count"] == 0


def test_filters_search_and_sorting(env: Env) -> None:
    zone(env, code="Z-1", name="Old Town", zone_type="residential")
    zone(env, code="Z-2", name="Harbour", zone_type="industrial")
    off = zone(env, code="Z-3", name="Ring Road", zone_type="industrial")
    env.client.patch(f"{ZONES}/{off['id']}", json={"is_active": False}, headers=env.manager)

    def codes(**params: Any) -> list[str]:
        body = env.client.get(ZONES, params=params, headers=env.manager).json()
        return [z["code"] for z in body["items"]]

    assert codes(zone_type="industrial", sort_by="code") == ["Z-2", "Z-3"]
    assert codes(active="true", sort_by="code") == ["Z-1", "Z-2"]
    assert codes(active="false") == ["Z-3"]
    assert codes(q="harb") == ["Z-2"]
    assert codes(q="%") == []  # the search is literal, not a LIKE wildcard
    assert codes(sort_by="name", order="desc") == ["Z-3", "Z-1", "Z-2"]
    page = env.client.get(ZONES, params={"page_size": 2, "sort_by": "code"}, headers=env.manager)
    assert page.json()["total"] == 3 and len(page.json()["items"]) == 2
