from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.db.session import get_engine
from app.main import create_app
from tests.conftest import SettingsFactory


def test_health_is_ok_and_does_not_touch_the_database(make_settings: SettingsFactory) -> None:
    # The configured database is unreachable (port 1); liveness must still succeed.
    client = TestClient(create_app(make_settings()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_503_when_database_unreachable(make_settings: SettingsFactory) -> None:
    app = create_app(make_settings())
    app.dependency_overrides[get_engine] = lambda: create_engine(
        "postgresql+psycopg://user:secret-pw@127.0.0.1:1/db", connect_args={"connect_timeout": 1}
    )
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"]["status"] == "failed"
    assert "secret-pw" not in response.text  # credentials never leak


def test_health_endpoints_are_not_under_api_prefix(make_settings: SettingsFactory) -> None:
    client = TestClient(create_app(make_settings()))
    assert client.get("/api/v1/health").status_code == 404
