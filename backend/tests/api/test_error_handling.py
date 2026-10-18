from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from pydantic import BaseModel

from app.core.exceptions import ConflictError, NotFoundError
from app.main import create_app
from tests.conftest import SettingsFactory


class Payload(BaseModel):
    quantity_kg: float


@pytest.fixture
def app(make_settings: SettingsFactory) -> FastAPI:
    app = create_app(make_settings())
    router = APIRouter()

    @router.get("/_test/not-found")
    def not_found() -> None:
        raise NotFoundError("Thing not found")

    @router.get("/_test/conflict")
    def conflict() -> None:
        raise ConflictError("Already exists", details=[{"field": "code"}])

    @router.get("/_test/boom")
    def boom() -> None:
        raise RuntimeError("database password is hunter2")

    @router.post("/_test/validate")
    def validate(payload: Payload) -> Payload:
        return payload

    app.include_router(router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def error(response: Response) -> dict[str, Any]:
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    result: dict[str, Any] = body["error"]
    return result


def test_domain_errors_are_structured(client: TestClient) -> None:
    response = client.get("/_test/not-found")
    assert response.status_code == 404
    assert error(response)["code"] == "not_found"

    response = client.get("/_test/conflict")
    assert response.status_code == 409
    assert error(response)["details"] == [{"field": "code"}]


def test_unknown_route_and_method_use_error_envelope(client: TestClient) -> None:
    assert error(client.get("/nope"))["code"] == "not_found"
    assert error(client.post("/health"))["code"] == "method_not_allowed"


def test_validation_errors_are_422_with_locations(client: TestClient) -> None:
    response = client.post("/_test/validate", json={"quantity_kg": "heavy"})
    assert response.status_code == 422
    err = error(response)
    assert err["code"] == "validation_error"
    assert err["details"][0]["location"] == ["body", "quantity_kg"]


def test_unhandled_errors_do_not_leak_internals(client: TestClient) -> None:
    response = client.get("/_test/boom")
    assert response.status_code == 500
    assert error(response)["message"] == "An unexpected error occurred"
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    generated = client.get("/health").headers["X-Request-ID"]
    assert len(generated) >= 8
    assert (
        client.get("/health", headers={"X-Request-ID": "client-supplied-1234"}).headers[
            "X-Request-ID"
        ]
        == "client-supplied-1234"
    )
    # Malformed ids (e.g. header injection attempts) are replaced.
    replaced = client.get("/health", headers={"X-Request-ID": "bad id with spaces"}).headers
    assert replaced["X-Request-ID"] != "bad id with spaces"


def test_error_body_carries_the_request_id(client: TestClient) -> None:
    response = client.get("/_test/not-found", headers={"X-Request-ID": "trace-me-12345"})
    assert error(response)["request_id"] == "trace-me-12345"
