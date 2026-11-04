"""The real ``get_db`` (the other API tests override it) must not starve requests of connections.

Found by a 100-user load run: with a synchronous dependency, finished requests held connections
while waiting for a free thread to close their session, and waiting requests held them while they
waited for the next thread, so the process stalled until the pool timeout. See
docs/testing/load-test-report.md.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from app.db import session as session_module
from app.main import create_app
from app.modules.auth.dependencies import CurrentPrincipal
from tests.conftest import SettingsFactory
from tests.fixtures.api import STRONG_PASSWORD, bearer, create_user

UNREAD = "/api/v1/notifications/unread-count"


@pytest.fixture
def small_pool_engine(db_engine: Engine) -> Iterator[Engine]:
    """Three connections only: far fewer than the concurrent requests below."""
    engine = create_engine(
        db_engine.url, pool_size=3, max_overflow=0, pool_timeout=5, pool_pre_ping=True
    )
    yield engine
    engine.dispose()


@pytest.fixture
def real_client(
    small_pool_engine: Engine, make_settings: SettingsFactory, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    factory = sessionmaker(bind=small_pool_engine, expire_on_commit=False)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: factory)
    return TestClient(create_app(make_settings()), raise_server_exceptions=False)


def test_get_db_does_not_need_a_thread_to_open_or_close() -> None:
    assert inspect.isasyncgenfunction(session_module.get_db)


def test_many_concurrent_requests_share_a_tiny_pool_without_stalling(
    real_client: TestClient, small_pool_engine: Engine, db_engine: Engine
) -> None:
    create_user(db_engine, email="pool@example.org")
    login = real_client.post(
        "/api/v1/auth/login", json={"email": "pool@example.org", "password": STRONG_PASSWORD}
    )
    assert login.status_code == 200, login.text
    headers = bearer(login.json()["access_token"])

    def call(_: int) -> int:
        return real_client.get(UNREAD, headers=headers).status_code

    with ThreadPoolExecutor(max_workers=24) as pool:
        statuses = list(pool.map(call, range(96)))

    assert statuses.count(200) == len(statuses), sorted(set(statuses))
    # Every connection went back to the pool: nothing is held after the responses.
    assert small_pool_engine.pool.checkedout() == 0  # type: ignore[attr-defined]


def test_authentication_returns_its_connection_before_the_handler_runs(
    small_pool_engine: Engine, db_engine: Engine, make_settings: SettingsFactory
) -> None:
    factory = sessionmaker(bind=small_pool_engine, expire_on_commit=False)
    app = create_app(make_settings())
    router = APIRouter()

    @router.get("/_test/held")
    def held(_: CurrentPrincipal) -> dict[str, int]:
        # Runs after authentication, before this handler has touched the database itself.
        return {"checked_out": small_pool_engine.pool.checkedout()}  # type: ignore[attr-defined]

    app.include_router(router)
    create_user(db_engine, email="release@example.org")
    session_module_factory = session_module.get_session_factory
    session_module.get_session_factory = lambda: factory  # type: ignore[assignment]
    try:
        client = TestClient(app, raise_server_exceptions=False)
        token = client.post(
            "/api/v1/auth/login", json={"email": "release@example.org", "password": STRONG_PASSWORD}
        ).json()["access_token"]
        response = client.get("/_test/held", headers=bearer(token))
    finally:
        session_module.get_session_factory = session_module_factory
    assert response.status_code == 200, response.text
    assert response.json() == {"checked_out": 0}
