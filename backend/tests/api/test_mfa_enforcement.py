"""Roles that must use two-step verification: only the set-up endpoints work until it is on."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.modules.auth import totp
from tests.fixtures.api import STRONG_PASSWORD, ClientFactory, bearer, create_user, login

AUTH = "/api/v1/auth"
PROTECTED = "/api/v1/admin/users"
ADMIN = "enforced.admin@example.org"
CITIZEN = "enforced.citizen@example.org"


@pytest.fixture
def enforced(make_client: ClientFactory) -> TestClient:
    return make_client(mfa_required_roles="administrator,manager")


def _enrol(client: TestClient, headers: dict[str, str]) -> list[str]:
    """Switch two-step verification on; returns the one-time recovery codes."""
    secret: str = client.post(f"{AUTH}/mfa/enroll", headers=headers).json()["secret"]
    code = totp.totp(secret, dt.datetime.now(dt.UTC).timestamp())
    done = client.post(f"{AUTH}/mfa/activate", json={"code": code}, headers=headers)
    assert done.status_code == 200, done.text
    codes: list[str] = done.json()["recovery_codes"]
    return codes


def test_privileged_user_without_mfa_can_only_reach_account_endpoints(
    enforced: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=ADMIN, roles=("administrator",))
    headers = bearer(login(enforced, ADMIN)["access_token"])

    blocked = enforced.get(PROTECTED, headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "mfa_enrollment_required"

    # the model endpoint needs sign-in only, and is held back as well
    assert enforced.get("/api/v1/classification/model", headers=headers).status_code == 403

    me = enforced.get(f"{AUTH}/me", headers=headers)
    assert me.status_code == 200 and me.json()["mfa_enrollment_required"] is True
    assert enforced.get(f"{AUTH}/mfa", headers=headers).status_code == 200


def test_login_response_tells_the_client_to_set_it_up(
    enforced: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=ADMIN, roles=("administrator",))
    body = login(enforced, ADMIN)
    assert body["user"]["mfa_enrollment_required"] is True


def test_finishing_enrolment_opens_everything_without_a_new_token(
    enforced: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=ADMIN, roles=("administrator",))
    headers = bearer(login(enforced, ADMIN)["access_token"])
    assert enforced.get(PROTECTED, headers=headers).status_code == 403
    _enrol(enforced, headers)
    assert enforced.get(PROTECTED, headers=headers).status_code == 200
    assert enforced.get(f"{AUTH}/me", headers=headers).json()["mfa_enrollment_required"] is False


def test_a_pending_unconfirmed_factor_does_not_count(
    enforced: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=ADMIN, roles=("administrator",))
    headers = bearer(login(enforced, ADMIN)["access_token"])
    assert enforced.post(f"{AUTH}/mfa/enroll", headers=headers).status_code == 200
    assert enforced.get(PROTECTED, headers=headers).status_code == 403


def test_roles_not_listed_are_not_affected(enforced: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=CITIZEN, roles=("citizen",))
    headers = bearer(login(enforced, CITIZEN)["access_token"])
    assert enforced.get(f"{AUTH}/me", headers=headers).json()["mfa_enrollment_required"] is False
    assert enforced.get("/api/v1/classification/model", headers=headers).status_code != 403


def test_a_second_role_does_not_escape_the_requirement(
    enforced: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=ADMIN, roles=("citizen", "manager"))
    headers = bearer(login(enforced, ADMIN)["access_token"])
    me = enforced.get(f"{AUTH}/me", headers=headers).json()
    assert me["mfa_enrollment_required"] is True


def test_required_roles_cannot_switch_it_off(enforced: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=ADMIN, roles=("administrator",))
    headers = bearer(login(enforced, ADMIN)["access_token"])
    codes = _enrol(enforced, headers)
    refused = enforced.post(
        f"{AUTH}/mfa/disable", json={"password": STRONG_PASSWORD, "code": codes[0]}, headers=headers
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "mfa_required_for_role"
    assert enforced.get(f"{AUTH}/mfa", headers=headers).json()["enabled"] is True


def test_citizens_may_still_switch_it_off(enforced: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=CITIZEN, roles=("citizen",))
    headers = bearer(login(enforced, CITIZEN)["access_token"])
    codes = _enrol(enforced, headers)
    done = enforced.post(
        f"{AUTH}/mfa/disable", json={"password": STRONG_PASSWORD, "code": codes[0]}, headers=headers
    )
    assert done.status_code == 204, done.text


def test_nothing_is_enforced_by_default_outside_production(
    make_client: ClientFactory, db_engine: Engine
) -> None:
    client = make_client()
    create_user(db_engine, email=ADMIN, roles=("administrator",))
    headers = bearer(login(client, ADMIN)["access_token"])
    assert client.get(PROTECTED, headers=headers).status_code == 200
