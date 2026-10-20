"""Fixtures for API tests that run against a real, migrated PostgreSQL database.

A template database is migrated once per test session; each test gets a clone of it
(``CREATE DATABASE ... TEMPLATE``), so tests are isolated, seeded (roles/permissions from the
migrations) and fast. All databases are dropped afterwards.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import CSRF_HEADER, CSRF_HEADER_VALUE, hash_password
from app.db.session import get_db
from app.main import create_app
from app.modules.users import repository as users
from tests.conftest import SettingsFactory
from tests.fixtures.database import DB_PREFIX, _admin_url, upgrade

CSRF = {CSRF_HEADER: CSRF_HEADER_VALUE}
STRONG_PASSWORD = "correct horse battery staple 42"


def _require_admin_url() -> URL:
    admin = _admin_url()
    if admin is None:
        import os

        if os.environ.get("CI"):
            pytest.fail("TEST_DATABASE_URL must be set when CI is set")
        pytest.skip("TEST_DATABASE_URL is not set; API tests need a PostgreSQL server")
    return admin


@pytest.fixture(scope="session")
def template_database_name() -> Iterator[str]:
    admin = _require_admin_url()
    name = f"{DB_PREFIX}tpl_{uuid.uuid4().hex[:10]}"
    admin_engine = create_engine(admin, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    template_engine = create_engine(admin.set(database=name))
    try:
        upgrade(template_engine)
        template_engine.dispose()  # a template must have no open connections
        yield name
    finally:
        template_engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin_engine.dispose()


@pytest.fixture
def db_engine(template_database_name: str) -> Iterator[Engine]:
    admin = _require_admin_url()
    name = f"{DB_PREFIX}{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(admin, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{template_database_name}"'))
    engine = create_engine(admin.set(database=name))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin_engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    with sessionmaker(bind=db_engine, expire_on_commit=False)() as session:
        yield session


ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make_client(db_engine: Engine, make_settings: SettingsFactory) -> ClientFactory:
    """Build a TestClient wired to this test's database. Each client has its own cookie jar."""
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    settings = make_settings()
    app = create_app(settings)

    def _get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db

    def _make(**overrides: Any) -> TestClient:
        if overrides:
            local = create_app(make_settings(**overrides))
            local.dependency_overrides[get_db] = _get_db
            return TestClient(local)
        return TestClient(app)

    return _make


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()


def create_user(
    engine: Engine,
    *,
    email: str,
    password: str = STRONG_PASSWORD,
    full_name: str = "Test Person",
    roles: tuple[str, ...] = ("citizen",),
    active: bool = True,
) -> uuid.UUID:
    """Insert a user directly (bypassing the API) with the given roles."""
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        user = users.add(
            session, email=email, password_hash=hash_password(password), full_name=full_name
        )
        user.is_active = active
        for name in roles:
            role = users.get_role_by_name(session, name)
            assert role is not None, f"role {name} not seeded"
            users.assign_role(session, user_id=user.id, role_id=role.id)
        session.commit()
        return user.id


def login(client: TestClient, email: str, password: str = STRONG_PASSWORD) -> dict[str, Any]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
