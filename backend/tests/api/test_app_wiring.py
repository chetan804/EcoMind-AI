from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import SettingsFactory


def test_openapi_is_served_under_the_api_version_prefix_outside_production(
    make_settings: SettingsFactory,
) -> None:
    client = TestClient(create_app(make_settings()))
    assert client.get("/api/v1/openapi.json").status_code == 200


def test_api_docs_are_disabled_in_production(make_settings: SettingsFactory) -> None:
    settings = make_settings(
        environment="production",
        secret_key="a-production-grade-random-secret-value-98765",
        refresh_cookie_secure=True,
        cors_allowed_origins="https://app.example.org",
    )
    client = TestClient(create_app(settings))
    assert client.get("/api/v1/openapi.json").status_code == 404
    assert client.get("/api/v1/docs").status_code == 404


def test_cors_allows_only_configured_origins(make_settings: SettingsFactory) -> None:
    client = TestClient(create_app(make_settings(cors_allowed_origins="http://allowed.test")))
    allowed = client.get("/health", headers={"Origin": "http://allowed.test"})
    denied = client.get("/health", headers={"Origin": "http://evil.test"})
    assert allowed.headers["access-control-allow-origin"] == "http://allowed.test"
    assert "access-control-allow-origin" not in denied.headers
