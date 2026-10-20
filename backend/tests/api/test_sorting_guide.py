"""Sorting guide API: seeded taxonomy, content management, visibility, authorisation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.fixtures.api import ClientFactory, bearer, create_user, login
from tests.fixtures.series import count

BASE = "/api/v1/sorting-guide"
TAXONOMY = {
    "cardboard", "glass", "metal", "paper", "plastic",
    "organic", "textile", "e_waste", "medical", "trash",
}  # fmt: skip


@dataclass
class Env:
    client: TestClient
    engine: Engine
    h: dict[str, dict[str, str]]


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    client = make_client()
    heads = {}
    for name in ("citizen", "manager", "administrator"):
        create_user(db_engine, email=f"{name}@example.org", roles=(name,))
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    return Env(client, db_engine, heads)


def categories(env: Env, who: str = "citizen", **params: Any) -> dict[str, dict[str, Any]]:
    page = env.client.get(
        f"{BASE}/categories", params={"page_size": 100, **params}, headers=env.h[who]
    )
    assert page.status_code == 200, page.text
    return {c["code"]: c for c in page.json()["items"]}


def new_guidance(env: Env, category: str, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "material_category_id": categories(env)[category]["id"],
        "disposal_method": "recycle",
        "title": "Rinse and recycle",
        "instructions": "Empty the container and place it in the dry recycling stream.",
        "source_reference": "Test municipality leaflet 2026",
    }
    body.update(over)
    response = env.client.post(f"{BASE}/guidance", json=body, headers=env.h["administrator"])
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def test_taxonomy_is_seeded_and_empty_of_invented_guidance(env: Env) -> None:
    cats = categories(env)
    assert set(cats) == TAXONOMY
    assert all(c["guidance_count"] == 0 and c["is_active"] for c in cats.values())
    guidance = env.client.get(f"{BASE}/guidance", headers=env.h["citizen"]).json()
    assert guidance["total"] == 0


def test_authentication_and_authorisation(env: Env) -> None:
    assert env.client.get(f"{BASE}/categories").status_code == 401
    body = {"code": "batteries", "name": "Batteries"}
    assert (
        env.client.post(f"{BASE}/categories", json=body, headers=env.h["citizen"]).status_code
        == 403
    )
    # managers hold sorting_guide:manage (migration 0002), citizens only sorting_guide:read
    assert (
        env.client.post(f"{BASE}/categories", json=body, headers=env.h["manager"]).status_code
        == 201
    )
    guidance_id = new_guidance(env, "glass")["id"]
    assert (
        env.client.patch(
            f"{BASE}/guidance/{guidance_id}", json={"title": "Hacked"}, headers=env.h["citizen"]
        ).status_code
        == 403
    )
    assert env.client.post(f"{BASE}/guidance", json={}, headers=env.h["citizen"]).status_code == 403


def test_category_crud_and_validation(env: Env) -> None:
    admin = env.h["administrator"]
    created = env.client.post(
        f"{BASE}/categories", json={"code": "Batteries ", "name": "Batteries"}, headers=admin
    )
    assert created.status_code == 201 and created.json()["code"] == "batteries"
    again = env.client.post(
        f"{BASE}/categories", json={"code": "batteries", "name": "Dup"}, headers=admin
    )
    assert again.status_code == 409
    for bad in (
        {"code": "9bad", "name": "x1"},
        {"code": "ok_code", "name": "x"},
        {"code": "a b", "name": "Name"},
    ):
        assert env.client.post(f"{BASE}/categories", json=bad, headers=admin).status_code == 422
    cid = created.json()["id"]
    patched = env.client.patch(
        f"{BASE}/categories/{cid}", json={"name": "Batteries (all)"}, headers=admin
    )
    assert patched.json()["name"] == "Batteries (all)"
    assert (
        env.client.patch(
            f"{BASE}/categories/{cid}", json={"is_active": None}, headers=admin
        ).status_code
        == 422
    )
    assert (
        env.client.patch(
            f"{BASE}/categories/{uuid.uuid4()}", json={"name": "Zed"}, headers=admin
        ).status_code
        == 404
    )


def test_inactive_content_is_hidden_from_readers_but_not_managers(env: Env) -> None:
    admin = env.h["administrator"]
    live = new_guidance(env, "glass", title="Glass bottles")
    draft = new_guidance(env, "glass", title="Glass draft", is_active=False)
    seen = env.client.get(
        f"{BASE}/guidance", params={"include_inactive": "true"}, headers=env.h["citizen"]
    )
    assert [g["title"] for g in seen.json()["items"]] == [
        "Glass bottles"
    ]  # flag ignored for citizens
    full = env.client.get(f"{BASE}/guidance", params={"include_inactive": "true"}, headers=admin)
    assert full.json()["total"] == 2
    assert (
        env.client.get(f"{BASE}/guidance/{draft['id']}", headers=env.h["citizen"]).status_code
        == 404
    )
    assert env.client.get(f"{BASE}/guidance/{draft['id']}", headers=admin).status_code == 200
    assert (
        env.client.get(f"{BASE}/guidance/{live['id']}", headers=env.h["citizen"]).status_code == 200
    )
    assert categories(env)["glass"]["guidance_count"] == 1  # active entries only

    # deactivating a category hides its guidance and the category itself from readers
    cid = categories(env)["glass"]["id"]
    env.client.patch(f"{BASE}/categories/{cid}", json={"is_active": False}, headers=admin)
    assert "glass" not in categories(env)
    assert "glass" in categories(env, "administrator", include_inactive="true")
    assert "glass" not in categories(env, "citizen", include_inactive="true")
    assert (
        env.client.get(f"{BASE}/guidance/{live['id']}", headers=env.h["citizen"]).status_code == 404
    )


def test_guidance_filters_search_and_source_flag(env: Env) -> None:
    new_guidance(env, "glass", title="Glass bottles", disposal_method="recycle")
    new_guidance(
        env, "organic", title="Food scraps", disposal_method="compost", source_reference=None
    )
    new_guidance(env, "e_waste", title="Old phones", disposal_method="e_waste_drop_off")
    h = env.h["citizen"]
    everything = env.client.get(f"{BASE}/guidance", headers=h).json()
    assert everything["total"] == 3
    by_title = {g["title"]: g for g in everything["items"]}
    assert by_title["Food scraps"]["has_source"] is False
    assert by_title["Glass bottles"]["has_source"] is True
    assert by_title["Old phones"]["category_code"] == "e_waste"
    one = env.client.get(
        f"{BASE}/guidance", params={"disposal_method": "compost"}, headers=h
    ).json()
    assert [g["title"] for g in one["items"]] == ["Food scraps"]
    cid = categories(env)["glass"]["id"]
    assert (
        env.client.get(f"{BASE}/guidance", params={"category_id": cid}, headers=h).json()["total"]
        == 1
    )
    found = env.client.get(f"{BASE}/guidance", params={"q": "phone"}, headers=h).json()
    assert [g["title"] for g in found["items"]] == ["Old phones"]
    assert (
        env.client.get(f"{BASE}/guidance", params={"q": "%"}, headers=h).json()["total"] == 0
    )  # literal
    desc = env.client.get(f"{BASE}/guidance", params={"order": "desc"}, headers=h).json()
    assert [g["title"] for g in desc["items"]] == ["Old phones", "Glass bottles", "Food scraps"]
    assert (
        env.client.get(
            f"{BASE}/guidance", params={"disposal_method": "burn"}, headers=h
        ).status_code
        == 422
    )


def test_guidance_validation_update_and_audit(env: Env) -> None:
    admin = env.h["administrator"]
    glass = categories(env)["glass"]["id"]
    for bad in (
        {"material_category_id": str(uuid.uuid4())},
        {"title": "x"},
        {"disposal_method": "burn"},
        {"unexpected": 1},
    ):
        body = {
            "material_category_id": glass,
            "disposal_method": "recycle",
            "title": "Valid title",
            "instructions": "Valid instructions.",
        } | bad
        assert env.client.post(f"{BASE}/guidance", json=body, headers=admin).status_code == 422, bad
    item = new_guidance(env, "glass")
    patched = env.client.patch(
        f"{BASE}/guidance/{item['id']}",
        json={"title": "Updated title", "is_active": False},
        headers=admin,
    )
    assert patched.status_code == 200 and patched.json()["title"] == "Updated title"
    assert patched.json()["is_active"] is False
    assert (
        env.client.patch(
            f"{BASE}/guidance/{item['id']}", json={"title": None}, headers=admin
        ).status_code
        == 422
    )
    assert (
        env.client.patch(
            f"{BASE}/guidance/{uuid.uuid4()}", json={"title": "Nothing"}, headers=admin
        ).status_code
        == 404
    )
    for action, n in (("sorting_guidance.created", 1), ("sorting_guidance.updated", 1)):
        assert count(env.engine, "select count(*) from audit_logs where action = :a", a=action) == n
