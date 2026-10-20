"""Baseline response headers set by the request middleware, on success and on error responses."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import SettingsFactory


@pytest.fixture
def client(make_settings: SettingsFactory) -> TestClient:
    return TestClient(create_app(make_settings()))


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
