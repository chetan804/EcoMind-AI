"""Refresh-token rotation, reuse detection, logout and password change."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from tests.fixtures.api import CSRF, STRONG_PASSWORD, ClientFactory, bearer, create_user, login

REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
CHANGE = "/api/v1/auth/change-password"
ME = "/api/v1/auth/me"
COOKIE = "ecomind_refresh"
PATH = "/api/v1/auth"


def _token(client: TestClient) -> str:
    value = client.cookies.get(COOKIE, path=PATH)
    assert value
    return value


def _age_rotation(db: Session, minutes: int = 60) -> None:
    """Pretend the rotation happened long ago (outside the benign-race grace window)."""
    db.execute(
        text(
            "UPDATE auth_sessions SET rotated_at = now() - make_interval(mins => :m) "
            "WHERE rotated_at IS NOT NULL"
        ),
        {"m": minutes},
    )
    db.commit()


def test_refresh_rotates_token_within_one_family(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email="r@example.org")
    first = login(client, "r@example.org")
    old = _token(client)

    response = client.post(REFRESH, headers=CSRF)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert _token(client) != old
    assert client.get(ME, headers=bearer(response.json()["access_token"])).status_code == 200
    assert response.json()["user"]["id"] == first["user"]["id"]

    rows = db_session.execute(
        text(
            "SELECT family_id, rotated_at IS NOT NULL AS rotated FROM auth_sessions "
            "ORDER BY created_at"
        )
    ).all()
    assert len(rows) == 2
    assert rows[0].family_id == rows[1].family_id
    assert [r.rotated for r in rows] == [True, False]


def test_refresh_requires_csrf_header_and_cookie(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email="c@example.org")
    login(client, "c@example.org")
    without_header = client.post(REFRESH)
    assert without_header.status_code == 403
    assert "set-cookie" not in without_header.headers  # did not rotate or clear anything

    anonymous = client.__class__(client.app)
    missing_cookie = anonymous.post(REFRESH, headers=CSRF)
    assert missing_cookie.status_code == 401
    assert missing_cookie.json()["error"]["code"] == "invalid_refresh_token"


def test_unknown_refresh_token_is_rejected_and_cookie_cleared(client: TestClient) -> None:
    client.cookies.set(COOKIE, "x" * 43, path=PATH)
    response = client.post(REFRESH, headers=CSRF)
    assert response.status_code == 401
    assert COOKIE in response.headers["set-cookie"] and "max-age=0" in (
        response.headers["set-cookie"].lower()
    )


def test_reused_rotated_token_revokes_the_whole_family(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email="thief@example.org")
    login(client, "thief@example.org")
    stolen = _token(client)
    assert client.post(REFRESH, headers=CSRF).status_code == 200  # victim rotates
    legit = _token(client)
    _age_rotation(db_session)

    attacker = client.__class__(client.app)
    attacker.cookies.set(COOKIE, stolen, path=PATH)
    replay = attacker.post(REFRESH, headers=CSRF)
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "refresh_token_reused"

    # The legitimate (newest) token is now dead too: the family was revoked.
    victim = client.__class__(client.app)
    victim.cookies.set(COOKIE, legit, path=PATH)
    assert victim.post(REFRESH, headers=CSRF).status_code == 401
    assert (
        db_session.execute(
            text("SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL")
        ).scalar_one()
        == 0
    )
    event = db_session.execute(
        text("SELECT actor_id FROM audit_logs WHERE action = 'auth.refresh_reuse_detected'")
    ).all()
    assert len(event) == 1


def test_immediate_replay_is_a_benign_race_and_does_not_revoke(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email="race@example.org")
    login(client, "race@example.org")
    first_token = _token(client)
    assert client.post(REFRESH, headers=CSRF).status_code == 200
    newest = _token(client)

    second_tab = client.__class__(client.app)
    second_tab.cookies.set(COOKIE, first_token, path=PATH)
    response = second_tab.post(REFRESH, headers=CSRF)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"  # not "reused"
    # Tabs share one cookie jar: clearing here would delete the winner's fresh cookie.
    assert "set-cookie" not in response.headers

    survivor = client.__class__(client.app)
    survivor.cookies.set(COOKIE, newest, path=PATH)
    assert survivor.post(REFRESH, headers=CSRF).status_code == 200  # family intact


def test_concurrent_refresh_of_one_token_has_exactly_one_winner(
    client: TestClient, db_engine: Engine
) -> None:
    """Row locking: two simultaneous uses of one token must not both succeed."""
    create_user(db_engine, email="conc@example.org")
    login(client, "conc@example.org")
    token = _token(client)

    def attempt(_: int) -> int:
        tab = client.__class__(client.app)
        tab.cookies.set(COOKIE, token, path=PATH)
        return tab.post(REFRESH, headers=CSRF).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(attempt, range(2)))
    assert statuses == [200, 401]


def test_expired_refresh_session_is_rejected(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email="old@example.org")
    login(client, "old@example.org")
    db_session.execute(
        text(
            "UPDATE auth_sessions SET created_at = now() - interval '30 days', "
            "expires_at = now() - interval '1 day'"
        )
    )
    db_session.commit()
    assert client.post(REFRESH, headers=CSRF).status_code == 401


def test_refresh_fails_for_deactivated_user_and_revokes(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    user_id = create_user(db_engine, email="off@example.org")
    login(client, "off@example.org")
    db_session.execute(text("UPDATE users SET is_active = false WHERE id = :i"), {"i": user_id})
    db_session.commit()
    assert client.post(REFRESH, headers=CSRF).status_code == 401
    assert (
        db_session.execute(
            text("SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL")
        ).scalar_one()
        == 0
    )


def test_logout_revokes_the_session_and_clears_the_cookie(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email="bye@example.org")
    login(client, "bye@example.org")
    token = _token(client)

    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert (
        db_session.execute(
            text("SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL")
        ).scalar_one()
        == 0
    )

    again = client.__class__(client.app)
    again.cookies.set(COOKIE, token, path=PATH)
    assert again.post(REFRESH, headers=CSRF).status_code == 401
    assert (
        db_session.execute(
            text("SELECT count(*) FROM audit_logs WHERE action = 'auth.logout'")
        ).scalar_one()
        == 1
    )


def test_logout_is_idempotent_and_csrf_protected(client: TestClient) -> None:
    assert client.post(LOGOUT, headers=CSRF).status_code == 204  # no cookie: still fine
    assert client.post(LOGOUT).status_code == 403


def test_logout_only_ends_the_presenting_device(
    make_client: ClientFactory, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email="multi@example.org")
    laptop, phone = make_client(), make_client()
    login(laptop, "multi@example.org")
    login(phone, "multi@example.org")
    assert laptop.post(LOGOUT, headers=CSRF).status_code == 204
    assert phone.post(REFRESH, headers=CSRF).status_code == 200


def test_change_password_revokes_other_sessions_and_keeps_this_one(
    make_client: ClientFactory, db_engine: Engine
) -> None:
    create_user(db_engine, email="pw@example.org")
    laptop, phone = make_client(), make_client()
    token = login(laptop, "pw@example.org")["access_token"]
    login(phone, "pw@example.org")
    new_password = "a brand new passphrase 77"

    response = laptop.post(
        CHANGE,
        headers=bearer(token),
        json={"current_password": STRONG_PASSWORD, "new_password": new_password},
    )
    assert response.status_code == 200
    assert laptop.post(REFRESH, headers=CSRF).status_code == 200  # this device continues
    assert phone.post(REFRESH, headers=CSRF).status_code == 401  # other device signed out

    anon = make_client()
    old = anon.post(
        "/api/v1/auth/login", json={"email": "pw@example.org", "password": STRONG_PASSWORD}
    )
    assert old.status_code == 401
    new = anon.post(
        "/api/v1/auth/login", json={"email": "pw@example.org", "password": new_password}
    )
    assert new.status_code == 200


def test_change_password_validates(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email="v@example.org")
    token = login(client, "v@example.org")["access_token"]
    headers = bearer(token)

    wrong = client.post(
        CHANGE,
        headers=headers,
        json={"current_password": "nope nope nope", "new_password": "another strong phrase 1"},
    )
    assert wrong.status_code == 401
    weak = client.post(
        CHANGE, headers=headers, json={"current_password": STRONG_PASSWORD, "new_password": "short"}
    )
    assert weak.status_code == 422 and weak.json()["error"]["code"] == "weak_password"
    same = client.post(
        CHANGE,
        headers=headers,
        json={"current_password": STRONG_PASSWORD, "new_password": STRONG_PASSWORD},
    )
    assert same.status_code == 422
    assert (
        client.post(CHANGE, json={"current_password": "a", "new_password": "b"}).status_code == 401
    )
    assert (
        db_session.execute(
            text("SELECT count(*) FROM audit_logs WHERE action = 'auth.password_change_failed'")
        ).scalar_one()
        == 1
    )
