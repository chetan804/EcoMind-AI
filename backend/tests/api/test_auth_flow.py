"""Registration, login and current-user behaviour against a real database."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

import jwt
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.core.security import create_access_token
from tests.conftest import TEST_SECRET_KEY
from tests.fixtures.api import STRONG_PASSWORD, bearer, create_user, login

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def _register(client: TestClient, email: str = "ada@example.org", **overrides: Any) -> Response:
    payload: dict[str, Any] = {
        "email": email,
        "password": STRONG_PASSWORD,
        "full_name": "Ada Lovelace",
    }
    payload.update(overrides)
    return client.post(REGISTER, json=payload)


def test_register_creates_citizen_signs_in_and_sets_secure_cookie(
    client: TestClient, db_session: Session
) -> None:
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["user"]["email"] == "ada@example.org"
    assert body["user"]["roles"] == ["citizen"]
    assert "waste_reports:create" in body["user"]["permissions"]
    assert "users:manage" not in body["user"]["permissions"]
    assert "password" not in response.text and "$argon2" not in response.text
    assert response.headers["cache-control"] == "no-store"

    cookie = response.headers["set-cookie"].lower()
    assert "ecomind_refresh=" in cookie
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/api/v1/auth" in cookie

    # What is stored: an Argon2id hash and only the SHA-256 digest of the refresh token.
    stored_hash = db_session.execute(text("SELECT password_hash FROM users")).scalar_one()
    assert stored_hash.startswith("$argon2id$")
    raw = client.cookies.get("ecomind_refresh", path="/api/v1/auth")
    assert raw
    token_hash = db_session.execute(text("SELECT token_hash FROM auth_sessions")).scalar_one()
    assert token_hash == hashlib.sha256(raw.encode()).hexdigest() != raw


def test_register_normalizes_email_and_rejects_duplicates_case_insensitively(
    client: TestClient,
) -> None:
    assert _register(client, "Mixed.Case@Example.org").json()["user"]["email"] == (
        "mixed.case@example.org"
    )
    duplicate = _register(client, "MIXED.CASE@example.ORG")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_already_registered"


def test_register_cannot_choose_roles(client: TestClient, db_session: Session) -> None:
    """Privilege escalation through the public endpoint must be impossible."""
    for extra in ({"roles": ["administrator"]}, {"role": "administrator"}, {"is_active": True}):
        response = _register(client, **extra)
        assert response.status_code == 422, extra
    assert db_session.execute(text("SELECT count(*) FROM users")).scalar_one() == 0


def test_register_enforces_password_policy(client: TestClient, db_session: Session) -> None:
    cases = {
        "short": "Sh0rt!pw",
        "common": "password123456",
        "repetitive": "aaaaaaaaaaaaaaaa",
        "contains_email_local_part": "xx-adalovelace-xx-1",
    }
    for label, password in cases.items():
        response = _register(client, "adalovelace@example.org", password=password)
        assert response.status_code == 422, label
        error = response.json()["error"]
        assert error["code"] == "weak_password", label
        assert error["details"], label
    assert db_session.execute(text("SELECT count(*) FROM users")).scalar_one() == 0


def test_register_validates_email_and_name(client: TestClient) -> None:
    assert _register(client, "not-an-email").status_code == 422
    assert _register(client, full_name="   ").status_code == 422
    assert _register(client, password="x" * 2000).status_code == 422


def test_login_succeeds_case_insensitively_and_records_audit(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    user_id = create_user(db_engine, email="grace@example.org")
    body = login(client, "GRACE@Example.org")
    assert body["user"]["id"] == str(user_id)

    assert db_session.execute(
        text("SELECT last_login_at IS NOT NULL FROM users WHERE id = :i"), {"i": user_id}
    ).scalar_one()
    audit = db_session.execute(
        text("SELECT actor_id, request_id, changes FROM audit_logs WHERE action = 'auth.login'")
    ).one()
    assert audit.actor_id == user_id
    assert audit.request_id
    assert "grace@example.org" not in str(audit.changes)  # pseudonymised, never clear text


def test_login_failures_are_indistinguishable(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email="real@example.org")
    create_user(db_engine, email="inactive@example.org", active=False)
    attempts = [
        ("real@example.org", "wrong password entirely"),
        ("nobody@example.org", STRONG_PASSWORD),
        ("inactive@example.org", STRONG_PASSWORD),
        ("not-an-email", STRONG_PASSWORD),
    ]
    messages = set()
    for email, password in attempts:
        response = client.post(LOGIN, json={"email": email, "password": password})
        assert response.status_code == 401, email
        error = response.json()["error"]
        assert error["code"] == "invalid_credentials"
        messages.add(error["message"])
        assert "ecomind_refresh" not in response.headers.get("set-cookie", "")
    assert len(messages) == 1  # same message for every failure reason


def test_failed_login_is_audited_without_credentials(
    client: TestClient, db_session: Session
) -> None:
    client.post(LOGIN, json={"email": "Probe@Example.org", "password": "hunter2hunter2"})
    row = db_session.execute(
        text("SELECT changes::text AS c FROM audit_logs WHERE action = 'auth.login_failed'")
    ).one()
    digest = hashlib.sha256(b"probe@example.org").hexdigest()
    assert digest in row.c
    assert "probe@example.org" not in row.c.lower() and "hunter2" not in row.c


def test_me_returns_roles_and_permissions(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email="op@example.org", roles=("citizen", "collector"))
    token = login(client, "op@example.org")["access_token"]
    response = client.get(ME, headers=bearer(token))
    assert response.status_code == 200
    body = response.json()
    assert body["roles"] == ["citizen", "collector"]
    assert "collection:execute" in body["permissions"]  # union of both roles
    assert "waste_reports:create" in body["permissions"]


def test_me_requires_a_valid_access_token(client: TestClient, db_engine: Engine) -> None:
    user_id = create_user(db_engine, email="t@example.org")
    missing = client.get(ME)
    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert missing.json()["error"]["code"] == "unauthenticated"

    assert client.get(ME, headers=bearer("garbage")).status_code == 401

    expired = create_access_token(
        subject=user_id,
        secret_key=TEST_SECRET_KEY,
        expires_in=timedelta(minutes=1),
        now=utc_now() - timedelta(hours=1),
    )
    assert client.get(ME, headers=bearer(expired)).status_code == 401

    wrong_key = create_access_token(
        subject=user_id, secret_key="another-secret-key-0123456789abcdef!!", expires_in=timedelta(1)
    )
    assert client.get(ME, headers=bearer(wrong_key)).status_code == 401

    unsigned = jwt.encode({"sub": str(user_id), "type": "access"}, key="", algorithm="none")
    assert client.get(ME, headers=bearer(unsigned)).status_code == 401

    refresh_like = jwt.encode(
        {"sub": str(user_id), "type": "refresh", "iss": "ecomind-ai", "exp": 9999999999},
        TEST_SECRET_KEY,
        algorithm="HS256",
    )
    assert client.get(ME, headers=bearer(refresh_like)).status_code == 401


def test_deactivated_user_loses_access_immediately(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    user_id = create_user(db_engine, email="gone@example.org")
    token = login(client, "gone@example.org")["access_token"]
    assert client.get(ME, headers=bearer(token)).status_code == 200
    db_session.execute(text("UPDATE users SET is_active = false WHERE id = :i"), {"i": user_id})
    db_session.commit()
    assert client.get(ME, headers=bearer(token)).status_code == 401  # not at token expiry
