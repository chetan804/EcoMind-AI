import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.db.session import get_engine
from app.main import create_app
from tests.conftest import SettingsFactory

pytestmark = pytest.mark.integration


def client_for(engine: Engine, make_settings: SettingsFactory) -> TestClient:
    app = create_app(make_settings())
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


def test_ready_when_schema_is_at_head(
    migrated_engine: Engine, make_settings: SettingsFactory
) -> None:
    response = client_for(migrated_engine, make_settings).get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "database": {"status": "ok", "detail": None},
            "migrations": {"status": "ok", "detail": None},
        },
    }


def test_not_ready_when_database_has_no_schema(
    empty_engine: Engine, make_settings: SettingsFactory
) -> None:
    response = client_for(empty_engine, make_settings).get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["migrations"]["status"] == "failed"
    assert "alembic upgrade head" in body["checks"]["migrations"]["detail"]
