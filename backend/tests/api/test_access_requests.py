"""Role requests: nobody gets a privileged role by asking for it, only by an administrator's decision."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.fixtures.api import ClientFactory, bearer, create_user, login

BASE = "/api/v1/access-requests"
REASON = "I drive route 14 for the municipal collection contractor and need to log pickups."


class Env:
    def __init__(self, client: TestClient, engine: Engine) -> None:
        self.client, self.engine = client, engine
        self.ids: dict[str, Any] = {}
        self.h: dict[str, dict[str, str]] = {}
        for who, email, role in (
            ("citizen", "citizen@example.org", "citizen"),
            ("other", "other@example.org", "citizen"),
            ("admin", "admin@example.org", "administrator"),
            ("admin2", "admin2@example.org", "administrator"),
            ("manager", "manager@example.org", "manager"),
        ):
            self.ids[who] = create_user(engine, email=email, roles=(role,))
            self.h[who] = bearer(login(client, email)["access_token"])

    def ask(self, who: str = "citizen", role: str = "collector", **over: Any) -> Any:
        body: dict[str, Any] = {"requested_role": role, "reason": REASON}
        body.update(over)
        return self.client.post(BASE, json=body, headers=self.h[who])

    def decide(self, request_id: str, who: str = "admin", **body: Any) -> Any:
        return self.client.post(
            f"{BASE}/{request_id}/decision", json=body or {"approve": True}, headers=self.h[who]
        )

    def roles_of(self, who: str) -> set[str]:
        with self.engine.connect() as c:
            rows = c.execute(
                text(
                    "select r.name from roles r join user_roles ur on ur.role_id=r.id "
                    "where ur.user_id=:u"
                ),
                {"u": self.ids[who]},
            )
            return {n for (n,) in rows}

    def audit_count(self, action: str) -> int:
        with self.engine.connect() as c:
            return int(
                c.execute(
                    text("select count(*) from audit_logs where action=:a"), {"a": action}
                ).scalar_one()
            )


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    return Env(make_client(), db_engine)


def test_everything_requires_sign_in(env: Env) -> None:
    assert env.client.post(BASE, json={}).status_code == 401
    assert env.client.get(f"{BASE}/mine").status_code == 401
    assert env.client.get(BASE).status_code == 401


def test_a_citizen_can_ask_but_asking_changes_no_role(env: Env) -> None:
    response = env.ask()
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending" and body["requested_role"] == "collector"
    assert env.roles_of("citizen") == {"citizen"}
    assert env.audit_count("access_request.created") == 1
    mine = env.client.get(f"{BASE}/mine", headers=env.h["citizen"]).json()
    assert [r["id"] for r in mine] == [body["id"]]
    assert env.client.get(f"{BASE}/mine", headers=env.h["other"]).json() == []


def test_administrator_cannot_be_requested_and_input_is_validated(env: Env) -> None:
    assert env.ask(role="administrator").status_code == 422
    assert env.ask(role="citizen").status_code == 422
    assert env.ask(reason="too short").status_code == 422
    assert env.ask(extra="field").status_code == 422
    assert env.roles_of("citizen") == {"citizen"}


def test_only_one_open_request_and_no_request_for_a_held_role(env: Env) -> None:
    assert env.ask().status_code == 201
    second = env.ask(role="manager")
    assert second.status_code == 409 and second.json()["error"]["code"] == "role_request_pending"
    held = env.ask("manager", role="manager")
    assert held.status_code == 409 and held.json()["error"]["code"] == "role_already_held"


def test_only_administrators_review_or_decide(env: Env) -> None:
    request_id = env.ask().json()["id"]
    for who in ("citizen", "other", "manager"):
        assert env.client.get(BASE, headers=env.h[who]).status_code == 403
        assert env.decide(request_id, who).status_code == 403
    assert env.roles_of("citizen") == {"citizen"}
    listed = env.client.get(BASE, headers=env.h["admin"]).json()
    assert listed["total"] == 1 and listed["items"][0]["requester_email"] == "citizen@example.org"
    filtered = env.client.get(f"{BASE}?status_filter=approved", headers=env.h["admin"]).json()
    assert filtered["total"] == 0


def test_approval_adds_the_role_keeps_citizen_audits_and_notifies(env: Env) -> None:
    request_id = env.ask().json()["id"]
    response = env.decide(request_id, approve=True, note="Welcome to the team.")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    assert env.roles_of("citizen") == {"citizen", "collector"}
    assert env.audit_count("access_request.approved") == 1
    notes = env.client.get("/api/v1/notifications", headers=env.h["citizen"]).json()
    assert any("approved" in n["title"] for n in notes["items"])
    # the new permissions are live for the next token the person gets
    me = env.client.get("/api/v1/auth/me", headers=env.h["citizen"]).json()
    assert "collector" in me["roles"]
    again = env.decide(request_id, approve=False, note="changed my mind")
    assert again.status_code == 409 and again.json()["error"]["code"] == "role_request_decided"
    assert env.roles_of("citizen") == {"citizen", "collector"}


def test_rejection_needs_a_reason_and_grants_nothing(env: Env) -> None:
    request_id = env.ask().json()["id"]
    assert env.decide(request_id, approve=False).status_code == 409
    rejected = env.decide(request_id, approve=False, note="Please ask your supervisor first.")
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert env.roles_of("citizen") == {"citizen"}
    assert env.audit_count("access_request.rejected") == 1
    # a decided request frees the person to ask again
    assert env.ask(role="manager").status_code == 201


def test_an_administrator_cannot_decide_their_own_request(env: Env) -> None:
    # administrators hold every role already, so use a manager who is also allowed to ask... via
    # the database: create a pending request for admin2 directly and try to decide it as admin2
    with env.engine.begin() as c:
        c.execute(
            text(
                "insert into role_requests (user_id, requested_role, reason) "
                "values (:u, 'collector', :r)"
            ),
            {"u": env.ids["admin2"], "r": REASON},
        )
        request_id = c.execute(
            text("select id from role_requests where user_id=:u"), {"u": env.ids["admin2"]}
        ).scalar_one()
    response = env.decide(str(request_id), "admin2")
    assert response.status_code == 403


def test_withdraw_is_private_and_final(env: Env) -> None:
    request_id = env.ask().json()["id"]
    assert (
        env.client.post(f"{BASE}/{request_id}/withdraw", headers=env.h["other"]).status_code == 404
    )
    done = env.client.post(f"{BASE}/{request_id}/withdraw", headers=env.h["citizen"])
    assert done.status_code == 200 and done.json()["status"] == "withdrawn"
    assert env.decide(request_id).status_code == 409
    assert env.roles_of("citizen") == {"citizen"}
    assert env.ask(role="facility_operator").status_code == 201


def test_unknown_request_ids_answer_404(env: Env) -> None:
    ghost = "00000000-0000-4000-8000-000000000001"
    assert env.decide(ghost).status_code == 404
    assert env.client.post(f"{BASE}/{ghost}/withdraw", headers=env.h["citizen"]).status_code == 404


def test_public_registration_still_yields_only_citizen(env: Env) -> None:
    response = env.client.post(
        "/api/v1/auth/register",
        json={
            "email": "newcomer@example.org",
            "password": "correct horse battery staple 42",
            "full_name": "New Comer",
            "roles": ["administrator"],
            "role": "administrator",
        },
    )
    assert response.status_code in (201, 422)
    if response.status_code == 201:
        assert response.json()["user"]["roles"] == ["citizen"]
