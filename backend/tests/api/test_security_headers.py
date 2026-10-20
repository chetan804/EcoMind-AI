"""Baseline response headers set by the request middleware, on success and on error responses."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import create_app
from tests.conftest import SettingsFactory


@pytest.fixture
def client(make_settings: SettingsFactory) -> Iterator[TestClient]:
    settings = make_settings()
    app = create_app(settings)
    # The sign-in check on /auth/me asks for a session before it looks at the credentials. The
    # engine is lazy and never connects (there is no token to look up), and this keeps the test
    # independent of any DATABASE_URL in the environment.
    engine = create_engine(settings.database_url)

    def _unused_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = _unused_session
    yield TestClient(app)
    engine.dispose()


@pytest.mark.parametrize(
    ("path", "status"),
    [("/health", 200), ("/api/v1/auth/me", 401), ("/api/v1/does-not-exist", 404)],
)
def test_responses_carry_the_baseline_headers(client: TestClient, path: str, status: int) -> None:
    response = client.get(path)
    assert response.status_code == status
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
