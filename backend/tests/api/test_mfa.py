"""TOTP two-factor authentication: enrolment, sign-in, recovery, replay, lockout, disabling."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_mfa_challenge_token
from app.modules.auth import mfa, totp
from tests.fixtures.api import STRONG_PASSWORD, ClientFactory, bearer, create_user, login
from tests.fixtures.series import count

AUTH = "/api/v1/auth"
EMAIL = "mfa.user@example.org"
KEY = "k" * 40


class Clock:
    """Controls the time the MFA module sees, so each test can use a fresh time step."""

    def __init__(self) -> None:
        self.now = dt.datetime.now(dt.UTC)

    def __call__(self) -> dt.datetime:
        return self.now

    def tick(self, steps: int = 1) -> None:
        self.now += dt.timedelta(seconds=totp.PERIOD * steps)


class Env:
    def __init__(self, client: TestClient, engine: Engine, clock: Clock) -> None:
        self.client, self.engine, self.clock = client, engine, clock
        self.user_id = create_user(engine, email=EMAIL, roles=("citizen",))
        self.access = login(client, EMAIL)["access_token"]
        self.h = bearer(self.access)

    def code(self, secret: str, steps_ahead: int = 0) -> str:
        return totp.totp(secret, self.clock.now.timestamp() + steps_ahead * totp.PERIOD)

    def enrol(self) -> tuple[str, list[str]]:
        started = self.client.post(f"{AUTH}/mfa/enroll", headers=self.h)
        assert started.status_code == 200, started.text
        secret: str = started.json()["secret"]
        done = self.client.post(
            f"{AUTH}/mfa/activate", json={"code": self.code(secret)}, headers=self.h
        )
        assert done.status_code == 200, done.text
        codes: list[str] = done.json()["recovery_codes"]
        return secret, codes

    def first_step(self, password: str = STRONG_PASSWORD) -> Any:
        return self.client.post(f"{AUTH}/login", json={"email": EMAIL, "password": password})

    def second_step(self, token: str, code: str) -> Any:
        return self.client.post(f"{AUTH}/mfa/verify", json={"mfa_token": token, "code": code})

    def challenge(self) -> str:
        body = self.first_step().json()
        assert body["mfa_required"] is True
        token: str = body["mfa_token"]
        return token


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(mfa, "utc_now", clock)
    return clock


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine, clock: Clock) -> Env:
    return Env(make_client(), db_engine, clock)


def test_requires_authentication(env: Env) -> None:
    for method, path in (
        ("GET", "/mfa"),
        ("POST", "/mfa/enroll"),
        ("POST", "/mfa/activate"),
        ("POST", "/mfa/disable"),
        ("POST", "/mfa/recovery-codes"),
    ):
        assert env.client.request(method, AUTH + path, json={}).status_code == 401, path


def test_enrolment_is_inactive_until_a_code_is_proven(env: Env) -> None:
    assert env.client.get(f"{AUTH}/mfa", headers=env.h).json() == {
        "enabled": False,
        "pending_enrollment": False,
        "enabled_at": None,
        "recovery_codes_remaining": 0,
    }
    started = env.client.post(f"{AUTH}/mfa/enroll", headers=env.h)
    body = started.json()
    assert started.headers["cache-control"] == "no-store"
    assert body["otpauth_uri"].startswith("otpauth://totp/EcoMind%20AI:")
    assert f"secret={body['secret']}" in body["otpauth_uri"]
    assert body["digits"] == 6 and body["period_seconds"] == 30

    # only an encrypted copy is stored
    with env.engine.connect() as conn:
        stored = conn.execute(text("SELECT secret_encrypted FROM mfa_factors")).scalar_one()
    assert body["secret"] not in stored

    status = env.client.get(f"{AUTH}/mfa", headers=env.h).json()
    assert status["enabled"] is False and status["pending_enrollment"] is True
    # a pending factor does not change sign-in
    assert "access_token" in env.first_step().json()

    wrong = env.client.post(f"{AUTH}/mfa/activate", json={"code": "000000"}, headers=env.h)
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "invalid_mfa_code"
    assert env.client.get(f"{AUTH}/mfa", headers=env.h).json()["enabled"] is False
    assert "access_token" in env.first_step().json()


def test_activation_needs_enrolment_and_cannot_repeat(env: Env) -> None:
    early = env.client.post(f"{AUTH}/mfa/activate", json={"code": "123456"}, headers=env.h)
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "mfa_enrollment_not_started"
    secret, codes = env.enrol()
    status = env.client.get(f"{AUTH}/mfa", headers=env.h).json()
    assert status["enabled"] is True and status["recovery_codes_remaining"] == 10
    assert status["enabled_at"] is not None and status["pending_enrollment"] is False
    assert len(codes) == 10 and len(set(codes)) == 10
    assert all(len(c) == 14 and c[4] == "-" and c[9] == "-" for c in codes)
    again = env.client.post(f"{AUTH}/mfa/enroll", headers=env.h)
    assert again.status_code == 409 and again.json()["error"]["code"] == "mfa_already_enabled"
    reuse = env.client.post(
        f"{AUTH}/mfa/activate", json={"code": env.code(secret, 1)}, headers=env.h
    )
    assert reuse.status_code == 409
    # recovery codes are stored only as hashes
    with env.engine.connect() as conn:
        hashes = set(conn.execute(text("SELECT code_hash FROM mfa_recovery_codes")).scalars())
    assert len(hashes) == 10 and not (hashes & ({c.replace("-", "") for c in codes} | set(codes)))


def test_sign_in_needs_the_second_step(env: Env) -> None:
    secret, _ = env.enrol()
    first = env.first_step()
    body = first.json()
    assert first.status_code == 200 and body["mfa_required"] is True
    assert "access_token" not in body and body["expires_in"] == 300
    assert "ecomind_refresh" not in first.headers.get("set-cookie", "")
    assert first.headers["cache-control"] == "no-store"

    token = body["mfa_token"]
    # the challenge is not an access token
    assert env.client.get(f"{AUTH}/me", headers=bearer(token)).status_code == 401

    env.clock.tick()  # the activation code used the current step; sign in with the next one
    done = env.second_step(token, env.code(secret))
    assert done.status_code == 200, done.text
    assert "ecomind_refresh=" in done.headers["set-cookie"]
    access = done.json()["access_token"]
    assert env.client.get(f"{AUTH}/me", headers=bearer(access)).json()["email"] == EMAIL
    assert (
        count(env.engine, "SELECT count(*) FROM audit_logs WHERE action='auth.mfa_succeeded'") == 1
    )


def test_wrong_password_never_reveals_the_second_step(env: Env) -> None:
    env.enrol()
    bad = env.first_step(password="Not-the-password-123")
    assert bad.status_code == 401 and "mfa" not in bad.text.lower()


def test_a_code_cannot_be_replayed(env: Env) -> None:
    secret, _ = env.enrol()
    env.clock.tick()
    code = env.code(secret)
    assert env.second_step(env.challenge(), code).status_code == 200
    replay = env.second_step(env.challenge(), code)
    assert replay.status_code == 401 and replay.json()["error"]["code"] == "invalid_mfa_code"
    # the previous step is also refused, the next one works
    assert env.second_step(env.challenge(), env.code(secret, -1)).status_code == 401
    assert env.second_step(env.challenge(), env.code(secret, 1)).status_code == 200


def test_invalid_challenges_are_rejected(env: Env) -> None:
    secret, _ = env.enrol()
    env.clock.tick()
    code = env.code(secret)
    key = env_secret_key(env)
    user = str(env.user_id)
    expired = create_mfa_challenge_token(
        subject=user, secret_key=key, expires_in=dt.timedelta(seconds=-5)
    )
    wrong_type = create_access_token(
        subject=user, secret_key=key, expires_in=dt.timedelta(minutes=5)
    )
    other_user = create_mfa_challenge_token(
        subject=str(uuid.uuid4()), secret_key=key, expires_in=dt.timedelta(minutes=5)
    )
    forged = create_mfa_challenge_token(
        subject=user, secret_key="x" * 40, expires_in=dt.timedelta(minutes=5)
    )
    for token in (expired, wrong_type, other_user, forged, "garbage.token.value"):
        response = env.second_step(token, code)
        assert response.status_code == 401, token
        assert response.json()["error"]["code"] == "invalid_mfa_code"
    # none of them consumed the real code
    assert env.second_step(env.challenge(), code).status_code == 200


def env_secret_key(env: Env) -> str:
    return str(env.client.app.state.settings.secret_key.get_secret_value())  # type: ignore[attr-defined]


def test_users_without_mfa_cannot_complete_a_challenge(env: Env) -> None:
    key = env_secret_key(env)
    token = create_mfa_challenge_token(
        subject=str(env.user_id), secret_key=key, expires_in=dt.timedelta(minutes=5)
    )
    assert env.second_step(token, "123456").status_code == 401


def test_five_wrong_codes_lock_the_second_step(env: Env) -> None:
    secret, _ = env.enrol()
    env.clock.tick()
    token = env.challenge()
    for _ in range(5):
        assert env.second_step(token, "000000").status_code == 401
    locked = env.second_step(token, env.code(secret))
    assert locked.status_code == 429 and int(locked.headers["retry-after"]) >= 1


def test_recovery_codes_work_once_and_count_down(env: Env) -> None:
    _, codes = env.enrol()
    assert env.second_step(env.challenge(), codes[0].lower().replace("-", " ")).status_code == 200
    again = env.second_step(env.challenge(), codes[0])
    assert again.status_code == 401
    assert env.client.get(f"{AUTH}/mfa", headers=env.h).json()["recovery_codes_remaining"] == 9
    assert env.second_step(env.challenge(), codes[1]).status_code == 200
    assert env.second_step(env.challenge(), "ABCD-EFGH-JKLM").status_code == 401


def test_deactivated_user_cannot_finish_sign_in(env: Env) -> None:
    secret, _ = env.enrol()
    token = env.challenge()
    env.clock.tick()
    with Session(env.engine) as db:
        db.execute(text("UPDATE users SET is_active = false"))
        db.commit()
    assert env.second_step(token, env.code(secret)).status_code == 401


def test_disabling_needs_password_and_code(env: Env) -> None:
    secret, codes = env.enrol()
    env.clock.tick()
    url = f"{AUTH}/mfa/disable"
    bad_pw = env.client.post(
        url, json={"password": "wrong-password-123", "code": env.code(secret)}, headers=env.h
    )
    assert bad_pw.status_code == 401
    bad_code = env.client.post(
        url, json={"password": STRONG_PASSWORD, "code": "000000"}, headers=env.h
    )
    assert bad_code.status_code == 422
    assert env.client.get(f"{AUTH}/mfa", headers=env.h).json()["enabled"] is True
    ok = env.client.post(
        url, json={"password": STRONG_PASSWORD, "code": env.code(secret)}, headers=env.h
    )
    assert ok.status_code == 204
    assert env.client.get(f"{AUTH}/mfa", headers=env.h).json()["enabled"] is False
    assert count(env.engine, "SELECT count(*) FROM mfa_recovery_codes") == 0
    assert "access_token" in env.first_step().json()
    again = env.client.post(
        url, json={"password": STRONG_PASSWORD, "code": codes[0]}, headers=env.h
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "mfa_not_enabled"
    for action in ("auth.mfa_enabled", "auth.mfa_disabled"):
        assert count(env.engine, "SELECT count(*) FROM audit_logs WHERE action=:a", a=action) == 1


def test_a_recovery_code_can_disable_mfa(env: Env) -> None:
    _, codes = env.enrol()
    ok = env.client.post(
        f"{AUTH}/mfa/disable", json={"password": STRONG_PASSWORD, "code": codes[3]}, headers=env.h
    )
    assert ok.status_code == 204


def test_regenerating_recovery_codes_invalidates_the_old_ones(env: Env) -> None:
    secret, old = env.enrol()
    env.clock.tick()
    url = f"{AUTH}/mfa/recovery-codes"
    assert (
        env.client.post(
            url, json={"password": "wrong-password-123", "code": env.code(secret)}, headers=env.h
        ).status_code
        == 401
    )
    fresh = env.client.post(
        url, json={"password": STRONG_PASSWORD, "code": env.code(secret)}, headers=env.h
    )
    assert fresh.status_code == 200
    new = fresh.json()["recovery_codes"]
    assert len(new) == 10 and not set(new) & set(old)
    assert env.second_step(env.challenge(), old[0]).status_code == 401
    assert env.second_step(env.challenge(), new[0]).status_code == 200


def test_administrator_can_reset_a_locked_out_user(
    make_client: ClientFactory, db_engine: Engine, clock: Clock
) -> None:
    client = make_client()
    env = Env(client, db_engine, clock)
    env.enrol()
    create_user(db_engine, email="admin@example.org", roles=("administrator",))
    admin = bearer(login(client, "admin@example.org")["access_token"])
    target = f"/api/v1/admin/users/{env.user_id}"
    assert client.get(target, headers=admin).json()["mfa_enabled"] is True

    denied = client.post(f"{target}/reset-mfa", json={"reason": "lost phone"}, headers=env.h)
    assert denied.status_code == 403
    done = client.post(
        f"{target}/reset-mfa", json={"reason": "Lost phone and codes"}, headers=admin
    )
    assert done.status_code == 200 and done.json()["mfa_enabled"] is False
    assert count(db_engine, "SELECT count(*) FROM mfa_factors") == 0
    assert "access_token" in env.first_step().json()
    log = client.get(
        "/api/v1/admin/audit-logs", params={"action": "user.mfa_reset"}, headers=admin
    ).json()
    assert log["total"] == 1 and log["items"][0]["changes"]["reason"] == "Lost phone and codes"
