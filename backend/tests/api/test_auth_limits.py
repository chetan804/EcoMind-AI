"""Brute-force and abuse limits (derived from the audit log, shared across workers)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.modules.auth import policy
from tests.fixtures.api import STRONG_PASSWORD, ClientFactory, create_user

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/register"


def _fail(client: TestClient, email: str) -> int:
    return client.post(LOGIN, json={"email": email, "password": "definitely wrong 1"}).status_code


def test_account_is_temporarily_locked_after_repeated_failures(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email="victim@example.org")
    create_user(db_engine, email="bystander@example.org")
    for _ in range(policy.MAX_FAILED_LOGINS_PER_EMAIL):
        assert _fail(client, "victim@example.org") == 401

    # Even the correct password is refused while locked, and the response says when to retry.
    locked = client.post(LOGIN, json={"email": "victim@example.org", "password": STRONG_PASSWORD})
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(locked.headers["retry-after"]) <= int(policy.LOGIN_WINDOW.total_seconds()) + 1

    # Other accounts are unaffected, and locked attempts do not extend the lock.
    ok = client.post(LOGIN, json={"email": "bystander@example.org", "password": STRONG_PASSWORD})
    assert ok.status_code == 200
    failures = db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE action = 'auth.login_failed'")
    ).scalar_one()
    assert failures == policy.MAX_FAILED_LOGINS_PER_EMAIL


def test_lock_applies_to_unknown_emails_too(client: TestClient) -> None:
    """Otherwise the lock itself would reveal which emails are registered."""
    for _ in range(policy.MAX_FAILED_LOGINS_PER_EMAIL):
        _fail(client, "ghost@example.org")
    assert _fail(client, "ghost@example.org") == 429


def test_lock_expires_after_the_window(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email="later@example.org")
    for _ in range(policy.MAX_FAILED_LOGINS_PER_EMAIL):
        _fail(client, "later@example.org")
    assert _fail(client, "later@example.org") == 429
    db_session.execute(text("UPDATE audit_logs SET occurred_at = now() - interval '16 minutes'"))
    db_session.commit()
    ok = client.post(LOGIN, json={"email": "later@example.org", "password": STRONG_PASSWORD})
    assert ok.status_code == 200


def test_successful_login_resets_the_failure_count(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email="forgetful@example.org")
    for _ in range(policy.MAX_FAILED_LOGINS_PER_EMAIL - 1):
        _fail(client, "forgetful@example.org")
    ok = client.post(LOGIN, json={"email": "forgetful@example.org", "password": STRONG_PASSWORD})
    assert ok.status_code == 200
    for _ in range(policy.MAX_FAILED_LOGINS_PER_EMAIL - 1):
        assert _fail(client, "forgetful@example.org") == 401  # still below the limit


def test_failures_are_limited_per_address_across_many_emails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(policy, "MAX_FAILED_LOGINS_PER_IP", 4)
    for index in range(4):
        assert _fail(client, f"spray{index}@example.org") == 401  # password spraying
    assert _fail(client, "spray99@example.org") == 429


def test_registrations_are_limited_per_address(make_client: ClientFactory) -> None:
    client = make_client(registration_limit_per_ip_per_hour=2)
    for index in range(2):
        response = client.post(
            REGISTER,
            json={
                "email": f"n{index}@example.org",
                "password": STRONG_PASSWORD,
                "full_name": "N N",
            },
        )
        assert response.status_code == 201
    blocked = client.post(
        REGISTER,
        json={"email": "n9@example.org", "password": STRONG_PASSWORD, "full_name": "N N"},
    )
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers
