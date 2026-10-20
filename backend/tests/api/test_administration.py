"""Administration: user and role management, audit log, system information."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.security import CSRF_HEADER, CSRF_HEADER_VALUE
from app.modules.administration import service
from app.modules.administration.schemas import ReasonRequest, RolesRequest
from app.modules.auth.dependencies import Principal
from tests.fixtures.api import STRONG_PASSWORD, ClientFactory, bearer, create_user, login

BASE = "/api/v1/admin"


class Env:
    def __init__(self, client: TestClient, engine: Engine) -> None:
        self.client, self.engine = client, engine
        self.ids: dict[str, uuid.UUID] = {}
        self.h: dict[str, dict[str, str]] = {}
        for who, role in (
            ("admin", "administrator"),
            ("admin2", "administrator"),
            ("manager", "manager"),
            ("citizen", "citizen"),
            ("target", "citizen"),
        ):
            email = f"{who}@example.org"
            self.ids[who] = create_user(
                engine, email=email, roles=(role,), full_name=f"Person {who.title()}"
            )
        for who in ("admin", "manager", "citizen"):
            self.h[who] = bearer(login(client, f"{who}@example.org")["access_token"])

    def call(self, method: str, path: str, who: str = "admin", **kwargs: Any) -> Any:
        return self.client.request(method, BASE + path, headers=self.h[who], **kwargs)

    def audit(self, **params: Any) -> list[dict[str, Any]]:
        response = self.call("GET", "/audit-logs", params=params)
        assert response.status_code == 200, response.text
        items: list[dict[str, Any]] = response.json()["items"]
        return items


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    return Env(make_client(), db_engine)


def test_permissions(env: Env) -> None:
    uid = env.ids["target"]
    # (method, path, roles that may call it): managers hold users:read but nothing else here
    endpoints = [
        ("GET", "/users", ("manager", "admin")),
        ("GET", f"/users/{uid}", ("manager", "admin")),
        ("GET", "/roles", ("manager", "admin")),
        ("GET", "/audit-logs", ("admin",)),
        ("GET", "/system", ("admin",)),
    ]
    for method, path, allowed in endpoints:
        assert env.client.request(method, BASE + path).status_code == 401, path
        for who in ("citizen", "manager", "admin"):
            expected = 200 if who in allowed else 403
            assert env.call(method, path, who).status_code == expected, (path, who)
    body = {"reason": "testing access"}
    for path in (f"/users/{uid}/deactivate", f"/users/{uid}/activate"):
        assert env.call("POST", path, "manager", json=body).status_code == 403
    roles = {"roles": ["manager"], "reason": "testing access"}
    assert env.call("PUT", f"/users/{uid}/roles", "manager", json=roles).status_code == 403


def test_user_list_filters_and_never_exposes_credentials(env: Env) -> None:
    everything = env.call("GET", "/users").json()
    assert everything["total"] == 5
    assert "password" not in str(everything).lower()
    by_role = env.call("GET", "/users", params={"role": "administrator"}).json()
    assert {u["email"] for u in by_role["items"]} == {"admin@example.org", "admin2@example.org"}
    assert env.call("GET", "/users", params={"q": "TARGET"}).json()["total"] == 1
    page = env.call("GET", "/users", params={"page_size": 2, "page": 3}).json()
    assert len(page["items"]) == 1 and page["total"] == 5
    assert env.call("GET", "/users", params={"is_active": "false"}).json()["total"] == 0
    assert env.call("GET", f"/users/{uuid.uuid4()}").status_code == 404


def test_roles_catalogue_lists_permissions_and_holders(env: Env) -> None:
    roles = {r["name"]: r for r in env.call("GET", "/roles").json()}
    assert set(roles) >= {"citizen", "collector", "facility_operator", "manager", "administrator"}
    assert roles["administrator"]["user_count"] == 2
    assert "waste_reports:create" in roles["citizen"]["permissions"]
    assert "users:manage" not in roles["manager"]["permissions"]
    assert "users:manage" in roles["administrator"]["permissions"]


def test_role_change_takes_effect_immediately_and_is_audited(env: Env) -> None:
    target = login(env.client, "target@example.org")["access_token"]
    analytics = "/api/v1/analytics/overview"
    assert env.client.get(analytics, headers=bearer(target)).status_code == 403

    uid = env.ids["target"]
    body = {"roles": ["manager", "citizen"], "reason": "Promoted to run the depot"}
    response = env.call("PUT", f"/users/{uid}/roles", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["roles"] == ["citizen", "manager"]
    # the same access token now carries the new permissions: they are read on every request
    assert env.client.get(analytics, headers=bearer(target)).status_code == 200

    entry = env.audit(action="user.roles_changed", entity_id=str(uid))[0]
    assert entry["changes"] == {
        "before": ["citizen"],
        "after": ["citizen", "manager"],
        "reason": "Promoted to run the depot",
    }
    assert entry["actor_email"] == "admin@example.org" and entry["entity_type"] == "user"


@pytest.mark.parametrize(
    "body",
    [
        {"roles": [], "reason": "no roles at all"},
        {"roles": ["citizen"]},
        {"roles": ["citizen"], "reason": "x"},
        {"roles": ["citizen"], "reason": "valid reason", "is_active": True},
    ],
)
def test_role_change_validation(env: Env, body: dict[str, Any]) -> None:
    uid = env.ids["target"]
    assert env.call("PUT", f"/users/{uid}/roles", json=body).status_code == 422


def test_unknown_role_and_unknown_user(env: Env) -> None:
    uid = env.ids["target"]
    bad = env.call("PUT", f"/users/{uid}/roles", json={"roles": ["superuser"], "reason": "try it"})
    assert bad.status_code == 422 and "superuser" in bad.text
    gone = env.call(
        "PUT", f"/users/{uuid.uuid4()}/roles", json={"roles": ["citizen"], "reason": "try it"}
    )
    assert gone.status_code == 404
    assert env.audit(action="user.roles_changed") == []


def test_administrators_cannot_modify_themselves(env: Env) -> None:
    me = env.ids["admin"]
    for response in (
        env.call("PUT", f"/users/{me}/roles", json={"roles": ["citizen"], "reason": "demote me"}),
        env.call("POST", f"/users/{me}/deactivate", json={"reason": "lock myself out"}),
    ):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "self_modification_forbidden"
    assert env.call("GET", f"/users/{me}").json()["roles"] == ["administrator"]


def test_last_active_administrator_is_protected(env: Env, db_session: Session) -> None:
    # admin removes admin2: allowed, one administrator remains
    other = env.ids["admin2"]
    ok = env.call(
        "PUT", f"/users/{other}/roles", json={"roles": ["citizen"], "reason": "step down"}
    )
    assert ok.status_code == 200
    # a different (hypothetical) caller with users:manage now tries to remove the only one left
    caller = Principal(
        user_id=uuid.uuid4(),
        email="x@example.org",
        full_name="X",
        roles=frozenset(),
        permissions=frozenset({"users:manage"}),
    )
    from app.modules.audit.service import RequestContext

    with pytest.raises(service.LastAdministratorError):
        service.set_roles(
            db_session,
            caller,
            env.ids["admin"],
            RolesRequest(roles=["citizen"], reason="remove last"),
            context=RequestContext(),
        )
    with pytest.raises(service.LastAdministratorError):
        service.set_active(
            db_session,
            caller,
            env.ids["admin"],
            active=False,
            reason=ReasonRequest(reason="remove last").reason,
            context=RequestContext(),
        )
    db_session.rollback()
    assert env.call("GET", f"/users/{env.ids['admin']}").json()["is_active"] is True


def test_deactivation_blocks_access_revokes_sessions_and_is_reversible(env: Env) -> None:
    uid = env.ids["target"]
    email = "target@example.org"
    access = login(env.client, email)["access_token"]  # also sets the refresh cookie
    csrf = {CSRF_HEADER: CSRF_HEADER_VALUE}
    me = "/api/v1/auth/me"
    assert env.client.get(me, headers=bearer(access)).status_code == 200

    assert env.call("POST", f"/users/{uid}/deactivate", json={"reason": "x"}).status_code == 422
    done = env.call("POST", f"/users/{uid}/deactivate", json={"reason": "Left the organisation"})
    assert done.status_code == 200 and done.json()["is_active"] is False

    assert env.client.get(me, headers=bearer(access)).status_code == 401
    assert env.client.post("/api/v1/auth/refresh", headers=csrf).status_code == 401
    attempt = env.client.post(
        "/api/v1/auth/login", json={"email": email, "password": STRONG_PASSWORD}
    )
    assert attempt.status_code == 401

    entry = env.audit(action="user.deactivated", entity_id=str(uid))[0]
    assert entry["changes"]["reason"] == "Left the organisation"
    assert entry["changes"]["sessions_revoked"] >= 1
    assert env.call("GET", "/users", params={"is_active": "false"}).json()["total"] == 1

    # repeating the call changes nothing and does not add another audit row
    env.call("POST", f"/users/{uid}/deactivate", json={"reason": "Left the organisation"})
    assert len(env.audit(action="user.deactivated", entity_id=str(uid))) == 1

    again = env.call("POST", f"/users/{uid}/activate", json={"reason": "Returned after leave"})
    assert again.json()["is_active"] is True
    assert (
        env.client.post(
            "/api/v1/auth/login", json={"email": email, "password": STRONG_PASSWORD}
        ).status_code
        == 200
    )
    assert len(env.audit(action="user.activated", entity_id=str(uid))) == 1


def test_audit_log_filters_and_order(env: Env) -> None:
    uid = env.ids["target"]
    env.call("PUT", f"/users/{uid}/roles", json={"roles": ["collector"], "reason": "field work"})
    env.call("POST", f"/users/{uid}/deactivate", json={"reason": "on leave"})
    everything = env.audit()
    stamps = [e["occurred_at"] for e in everything]
    assert stamps == sorted(stamps, reverse=True)
    mine = env.audit(entity_id=str(uid))
    assert [e["action"] for e in mine] == ["user.deactivated", "user.roles_changed"]
    admin_actions = env.audit(actor_id=str(env.ids["admin"]), entity_type="user")
    assert {e["action"] for e in admin_actions} >= {"user.deactivated", "user.roles_changed"}
    assert env.audit(action="no.such.action") == []
    future = env.call("GET", "/audit-logs", params={"occurred_from": "2999-01-01T00:00:00Z"})
    assert future.json()["total"] == 0
    assert env.call("GET", "/audit-logs", params={"entity_id": "not-a-uuid"}).status_code == 422


def test_system_info_exposes_no_secrets(env: Env) -> None:
    body = env.call("GET", "/system").json()
    text = str(body).lower()
    for forbidden in ("secret", "password", "postgresql", "database_url", "storage_path"):
        assert forbidden not in text, forbidden
    assert body["database_revision"]
    assert body["file_storage_backend"] == "local"
    assert body["reward_points_per_kg"] == 10
    assert body["active_model_version"] is None or isinstance(body["active_model_version"], str)
