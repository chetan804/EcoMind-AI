"""Server-side authorization: deny by default, decided from the database on every request."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import create_app
from app.modules.auth.dependencies import Principal, require_permissions
from tests.conftest import SettingsFactory
from tests.fixtures.api import bearer, create_user, login


def _app_with_probe_routes(engine: Engine, make_settings: SettingsFactory) -> FastAPI:
    app = create_app(make_settings())
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def _get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    probe = APIRouter()

    @probe.get("/probe/users")
    def users_only(
        principal: Annotated[Principal, Depends(require_permissions("users:manage"))],
    ) -> dict[str, str]:
        return {"who": principal.email}

    @probe.get("/probe/both")
    def needs_both(
        _: Annotated[
            Principal, Depends(require_permissions("waste_reports:create", "users:manage"))
        ],
    ) -> dict[str, bool]:
        return {"ok": True}

    app.include_router(probe, prefix="/api/v1")
    return app


def _client(engine: Engine, make_settings: SettingsFactory) -> TestClient:
    return TestClient(_app_with_probe_routes(engine, make_settings))


def test_anonymous_callers_get_401_not_403(
    db_engine: Engine, make_settings: SettingsFactory
) -> None:
    response = _client(db_engine, make_settings).get("/api/v1/probe/users")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_missing_permission_is_403_and_does_not_leak_the_permission_name(
    db_engine: Engine, make_settings: SettingsFactory
) -> None:
    create_user(db_engine, email="cit@example.org", roles=("citizen",))
    client = _client(db_engine, make_settings)
    token = login(client, "cit@example.org")["access_token"]
    response = client.get("/api/v1/probe/users", headers=bearer(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert "users:manage" not in response.text


def test_only_roles_that_grant_the_permission_pass(
    db_engine: Engine, make_settings: SettingsFactory
) -> None:
    expectations = {
        "citizen": 403,
        "collector": 403,
        "facility_operator": 403,
        "manager": 403,  # managers may read users but not manage them
        "administrator": 200,
    }
    client = _client(db_engine, make_settings)
    for role, expected in expectations.items():
        create_user(db_engine, email=f"{role}@example.org", roles=(role,))
        token = login(client, f"{role}@example.org")["access_token"]
        got = client.get("/api/v1/probe/users", headers=bearer(token)).status_code
        assert got == expected, role


def test_all_listed_permissions_are_required(
    db_engine: Engine, make_settings: SettingsFactory
) -> None:
    client = _client(db_engine, make_settings)
    create_user(db_engine, email="admin@example.org", roles=("administrator",))
    create_user(db_engine, email="citizen@example.org", roles=("citizen",))
    admin = login(client, "admin@example.org")["access_token"]
    citizen = login(client, "citizen@example.org")["access_token"]
    assert client.get("/api/v1/probe/both", headers=bearer(admin)).status_code == 200
    assert client.get("/api/v1/probe/both", headers=bearer(citizen)).status_code == 403


def test_role_changes_apply_to_existing_tokens_immediately(
    db_engine: Engine, make_settings: SettingsFactory, db_session: Session
) -> None:
    """Permissions are not baked into the token, so revocation is not delayed by token expiry."""
    user_id = create_user(db_engine, email="demoted@example.org", roles=("administrator",))
    client = _client(db_engine, make_settings)
    token = login(client, "demoted@example.org")["access_token"]
    assert client.get("/api/v1/probe/users", headers=bearer(token)).status_code == 200

    db_session.execute(text("DELETE FROM user_roles WHERE user_id = :i"), {"i": user_id})
    db_session.commit()
    assert client.get("/api/v1/probe/users", headers=bearer(token)).status_code == 403


def test_a_user_with_no_role_can_do_nothing(
    db_engine: Engine, make_settings: SettingsFactory
) -> None:
    create_user(db_engine, email="norole@example.org", roles=())
    client = _client(db_engine, make_settings)
    token = login(client, "norole@example.org")["access_token"]
    assert client.get("/api/v1/auth/me", headers=bearer(token)).json()["permissions"] == []
    assert client.get("/api/v1/probe/users", headers=bearer(token)).status_code == 403


def test_require_permissions_needs_at_least_one_permission() -> None:
    import pytest

    with pytest.raises(ValueError):
        require_permissions()


def test_password_hash_never_appears_in_any_auth_response(
    db_engine: Engine, make_settings: SettingsFactory
) -> None:
    client = _client(db_engine, make_settings)
    create_user(db_engine, email="leak@example.org")
    body = login(client, "leak@example.org")
    me = client.get("/api/v1/auth/me", headers=bearer(body["access_token"]))
    assert "argon2" not in str(body) + me.text and "password" not in me.text
