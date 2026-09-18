from fastapi.testclient import TestClient
import pytest

from app.core.config import load_settings
from app.main import app
import app.main as main


def settings_environment(**overrides: str) -> dict[str, str]:
    values = {
        "DATABASE_URL": "postgresql://test:test@localhost/ecomind_test",
        "SECRET_KEY": "test-secret-value-that-is-long-enough-for-production",
        "CORS_ORIGINS": "http://localhost:5173",
    }
    values.update(overrides)
    return values


def test_load_settings_rejects_unknown_environment():
    with pytest.raises(ValueError, match="ENVIRONMENT"):
        load_settings(settings_environment(ENVIRONMENT="staging"))


def test_load_settings_rejects_wildcard_cors_in_production():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        load_settings(settings_environment(ENVIRONMENT="production", CORS_ORIGINS="*"))


def test_load_settings_parses_valid_production_configuration():
    settings = load_settings(settings_environment(ENVIRONMENT="production"))
    assert settings.environment == "production"
    assert settings.cors_origins == ("http://localhost:5173",)


def test_liveness_is_independent_of_database():
    with TestClient(app) as client:
        response = client.get("/liveness")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_health_reports_available_database(monkeypatch):
    monkeypatch.setattr(main, "database_is_available", lambda engine: True)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "available"


@pytest.mark.parametrize(("path", "expected_status"), [("/health", "degraded"), ("/readiness", "not_ready")])
def test_database_endpoints_report_unavailable_database(monkeypatch, path, expected_status):
    monkeypatch.setattr(main, "database_is_available", lambda engine: False)
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 503
    assert response.json()["status"] == expected_status


def test_system_responses_include_request_and_security_headers():
    with TestClient(app) as client:
        response = client.get("/liveness", headers={"X-Request-ID": "test-id"})
    assert response.headers["X-Request-ID"] == "test-id"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
