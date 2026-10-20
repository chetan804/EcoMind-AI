"""Facilities: read for staff and citizens, management for managers only."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.fixtures.api import ClientFactory, bearer, create_user, login

URL = "/api/v1/facilities"


@dataclass
class Env:
    client: TestClient
    engine: Engine
    citizen: dict[str, str]
    operator: dict[str, str]
    manager: dict[str, str]


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    client = make_client()
    heads = {}
    for name, roles in (
        ("citizen", ("citizen",)),
        ("operator", ("facility_operator",)),
        ("manager", ("manager",)),
    ):
        create_user(db_engine, email=f"{name}@example.org", roles=roles)
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    return Env(client, db_engine, heads["citizen"], heads["operator"], heads["manager"])


def make(env: Env, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "code": "HYD-01",
        "name": "Hyderabad Processing Centre",
        "facility_type": "processing_center",
    }
    body.update(overrides)
    response = env.client.post(URL, json=body, headers=env.manager)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def test_authentication_and_authorization(env: Env) -> None:
    some = uuid.uuid4()
    assert env.client.get(URL).status_code == 401
    assert env.client.get(f"{URL}/{some}").status_code == 401
    assert env.client.post(URL, json={}).status_code == 401
    assert env.client.patch(f"{URL}/{some}", json={}).status_code == 401
    # reading is open to every signed-in role; changing is manager-only
    for who in (env.citizen, env.operator, env.manager):
        assert env.client.get(URL, headers=who).status_code == 200
    body = {"code": "NEW-1", "name": "Nope", "facility_type": "depot"}
    for who in (env.citizen, env.operator):
        assert env.client.post(URL, json=body, headers=who).status_code == 403
    created = make(env)
    for who in (env.citizen, env.operator):
        response = env.client.patch(f"{URL}/{created['id']}", json={"city": "X"}, headers=who)
        assert response.status_code == 403
    assert env.client.get(f"{URL}/{created['id']}", headers=env.manager).json()["city"] is None


def test_create_normalises_input_and_audits(env: Env) -> None:
    created = make(
        env,
        code="  hyd-02 ",
        name="  North Depot ",
        country_code="in",
        city="Hyderabad",
        latitude="17.4",
        longitude="78.5",
        daily_capacity_kg="12000.5",
        contact_email="ops@example.org",
    )
    assert created["code"] == "HYD-02" and created["name"] == "North Depot"
    assert created["country_code"] == "IN" and created["status"] == "active"
    assert float(created["daily_capacity_kg"]) == 12000.5
    assert created["contact_email"] == "ops@example.org"
    with env.engine.connect() as conn:
        entry = conn.execute(
            text("SELECT changes FROM audit_logs WHERE action='facility.created'")
        ).scalar_one()
    assert entry == {"code": "HYD-02", "facility_type": "processing_center"}


def test_duplicate_code_is_a_conflict_regardless_of_case(env: Env) -> None:
    make(env, code="DUP-1")
    again = env.client.post(
        URL,
        json={"code": "dup-1", "name": "Other", "facility_type": "depot"},
        headers=env.manager,
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "facility_code_taken"
    assert env.client.get(URL, headers=env.manager).json()["total"] == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"code": "x"},
        {"code": "-bad"},
        {"code": "has space"},
        {"code": "a"},
        {"code": "A" * 33},
        {"name": "x"},
        {"facility_type": "spaceport"},
        {"status": "exploded"},
        {"country_code": "IND"},
        {"country_code": "1N"},
        {"latitude": "95", "longitude": "0"},
        {"latitude": "5"},
        {"daily_capacity_kg": "0"},
        {"daily_capacity_kg": "-5"},
        {"contact_email": "not-an-email"},
        {"id": str(uuid.uuid4())},
        {"created_at": "2020-01-01T00:00:00Z"},
    ],
)
def test_invalid_create_bodies_are_rejected(env: Env, patch: dict[str, Any]) -> None:
    body = {"code": "OK-1", "name": "Valid", "facility_type": "depot", **patch}
    response = env.client.post(URL, json=body, headers=env.manager)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    with env.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM facilities")).scalar_one() == 0


def test_contact_email_is_only_visible_to_managers(env: Env) -> None:
    created = make(env, contact_email="private.person@example.org")
    one = f"{URL}/{created['id']}"
    assert env.client.get(one, headers=env.manager).json()["contact_email"] == (
        "private.person@example.org"
    )
    for who in (env.citizen, env.operator):
        assert env.client.get(one, headers=who).json()["contact_email"] is None
        listed = env.client.get(URL, headers=who)
        assert "private.person" not in listed.text


def test_get_unknown_or_malformed_id(env: Env) -> None:
    assert env.client.get(f"{URL}/{uuid.uuid4()}", headers=env.citizen).status_code == 404
    assert env.client.get(f"{URL}/nope", headers=env.citizen).status_code == 422


# --------------------------------------------------------------------------------- update


def test_patch_changes_only_the_sent_fields_and_records_a_diff(env: Env) -> None:
    created = make(env, city="Hyderabad", daily_capacity_kg="1000", contact_email="a@example.org")
    url = f"{URL}/{created['id']}"
    response = env.client.patch(
        url,
        json={"city": "Secunderabad", "status": "maintenance", "contact_email": "b@example.org"},
        headers=env.manager,
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["city"], body["status"]) == ("Secunderabad", "maintenance")
    assert body["name"] == created["name"] and float(body["daily_capacity_kg"]) == 1000
    with env.engine.connect() as conn:
        fields = conn.execute(
            text("SELECT changes FROM audit_logs WHERE action='facility.updated'")
        ).scalar_one()["fields"]
    assert fields["city"] == {"from": "Hyderabad", "to": "Secunderabad"}
    assert fields["status"] == {"from": "active", "to": "maintenance"}
    assert fields["contact_email"] == {"changed": True}  # the address itself is not logged
    assert "a@example.org" not in str(fields) and "b@example.org" not in str(fields)


def test_nullable_fields_can_be_cleared_but_required_ones_cannot(env: Env) -> None:
    created = make(env, city="Hyderabad", daily_capacity_kg="500")
    url = f"{URL}/{created['id']}"
    ok = env.client.patch(url, json={"city": None, "daily_capacity_kg": None}, headers=env.manager)
    assert ok.status_code == 200 and ok.json()["city"] is None
    for field in ("name", "facility_type", "status"):
        bad = env.client.patch(url, json={field: None}, headers=env.manager)
        assert bad.status_code == 422, field


def test_code_is_immutable_and_unknown_fields_are_rejected(env: Env) -> None:
    created = make(env)
    for body in ({"code": "CHANGED"}, {"id": str(uuid.uuid4())}, {"nonsense": 1}):
        response = env.client.patch(f"{URL}/{created['id']}", json=body, headers=env.manager)
        assert response.status_code == 422
    assert env.client.get(f"{URL}/{created['id']}", headers=env.manager).json()["code"] == "HYD-01"


def test_a_noop_patch_writes_no_audit_entry(env: Env) -> None:
    created = make(env, city="Hyderabad")
    response = env.client.patch(
        f"{URL}/{created['id']}",
        json={"city": "Hyderabad", "name": created["name"]},
        headers=env.manager,
    )
    assert response.status_code == 200
    with env.engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM audit_logs WHERE action='facility.updated'")
        ).scalar_one()
    assert count == 0


def test_setting_only_one_coordinate_is_a_422_and_changes_nothing(env: Env) -> None:
    created = make(env)
    url = f"{URL}/{created['id']}"
    response = env.client.patch(url, json={"latitude": "10.5"}, headers=env.manager)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unprocessable"
    assert env.client.get(url, headers=env.manager).json()["latitude"] is None
    both = env.client.patch(
        url, json={"latitude": "10.5", "longitude": "20.5"}, headers=env.manager
    )
    assert both.status_code == 200 and float(both.json()["longitude"]) == 20.5


def test_patch_unknown_facility_is_404(env: Env) -> None:
    response = env.client.patch(f"{URL}/{uuid.uuid4()}", json={"city": "X"}, headers=env.manager)
    assert response.status_code == 404


def test_facilities_are_deactivated_not_deleted(env: Env) -> None:
    created = make(env)
    assert env.client.delete(f"{URL}/{created['id']}", headers=env.manager).status_code == 405
    env.client.patch(f"{URL}/{created['id']}", json={"status": "inactive"}, headers=env.manager)
    body = env.client.get(f"{URL}/{created['id']}", headers=env.citizen).json()
    assert body["status"] == "inactive"


# -------------------------------------------------------------------------------- listing


@pytest.fixture
def seeded(env: Env) -> Env:
    make(env, code="A-1", name="Alpha Centre", city="Hyderabad", daily_capacity_kg="5000")
    make(env, code="B-2", name="beta Depot", facility_type="depot", city="Warangal")
    make(
        env,
        code="C-3",
        name="Gamma Point",
        facility_type="drop_off_point",
        city="hyderabad",
        status="maintenance",
        daily_capacity_kg="100",
    )
    return env


def _codes(env: Env, **params: Any) -> list[str]:
    response = env.client.get(URL, params=params, headers=env.citizen)
    assert response.status_code == 200, response.text
    return [f["code"] for f in response.json()["items"]]


def test_filters(seeded: Env) -> None:
    assert _codes(seeded, facility_type="depot") == ["B-2"]
    assert _codes(seeded, status="maintenance") == ["C-3"]
    assert _codes(seeded, city="HYDERABAD") == ["A-1", "C-3"]  # case-insensitive, exact
    assert _codes(seeded, city="Hyder") == []  # exact match, not prefix
    assert _codes(seeded, facility_type="depot", status="maintenance") == []
    for bad in ({"facility_type": "x"}, {"status": "x"}):
        assert seeded.client.get(URL, params=bad, headers=seeded.citizen).status_code == 422


def test_search_covers_name_code_and_city_and_is_literal(seeded: Env) -> None:
    assert _codes(seeded, q="beta") == ["B-2"]
    assert _codes(seeded, q="c-3") == ["C-3"]
    assert _codes(seeded, q="warang") == ["B-2"]
    assert _codes(seeded, q="%") == []
    assert _codes(seeded, q="_") == []
    assert _codes(seeded, q="' OR 1=1 --") == []


def test_sorting_and_stable_pagination(seeded: Env) -> None:
    assert _codes(seeded) == ["A-1", "B-2", "C-3"]  # default: name ascending, case-insensitive
    assert _codes(seeded, sort_by="name", order="desc") == ["C-3", "B-2", "A-1"]
    assert _codes(seeded, sort_by="daily_capacity_kg", order="asc") == ["C-3", "A-1", "B-2"]
    assert _codes(seeded, sort_by="daily_capacity_kg", order="desc") == ["A-1", "C-3", "B-2"]
    assert (
        seeded.client.get(
            URL, params={"sort_by": "contact_email"}, headers=seeded.citizen
        ).status_code
        == 422
    )
    pages = [_codes(seeded, page=p, page_size=2) for p in (1, 2, 3)]
    assert pages == [["A-1", "B-2"], ["C-3"], []]
    body = seeded.client.get(URL, params={"page_size": 2}, headers=seeded.citizen).json()
    assert body["total"] == 3 and body["page_size"] == 2
