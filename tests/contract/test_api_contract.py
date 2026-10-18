"""API contract: the generated OpenAPI document must follow docs/api/api-conventions.md and
agree with what the frontend consumes."""

import re
from pathlib import Path
from typing import Any

import pytest
from app.core.config import Settings
from app.main import create_app

REPO = Path(__file__).resolve().parents[2]
OPERATIONAL_PATHS = {"/health", "/ready"}


@pytest.fixture(scope="module")
def openapi() -> dict[str, Any]:
    app = create_app(Settings(_env_file=None))  # type: ignore[call-arg]  # values come from conftest env
    return app.openapi()


def test_all_application_routes_are_versioned(openapi: dict[str, Any]) -> None:
    unversioned = [
        path
        for path in openapi["paths"]
        if not path.startswith("/api/v1/") and path not in OPERATIONAL_PATHS
    ]
    assert unversioned == []


def test_operational_endpoints_are_documented(openapi: dict[str, Any]) -> None:
    assert set(openapi["paths"]) >= OPERATIONAL_PATHS
    ready = openapi["paths"]["/ready"]["get"]["responses"]
    assert {"200", "503"} <= set(ready)
    schemas = openapi["components"]["schemas"]
    assert set(schemas["LivenessResponse"]["properties"]) == {"status"}
    assert set(schemas["ReadinessResponse"]["required"]) == {"status", "checks"}


def test_error_envelope_schema_is_published(openapi: dict[str, Any]) -> None:
    schemas = openapi["components"]["schemas"]
    assert set(schemas["ErrorResponse"]["properties"]) == {"error"}
    assert set(schemas["ErrorBody"]["properties"]) == {"code", "message", "details", "request_id"}


def test_operation_ids_are_unique(openapi: dict[str, Any]) -> None:
    ids = [op["operationId"] for item in openapi["paths"].values() for op in item.values()]
    assert len(ids) == len(set(ids))


def test_frontend_readiness_schema_matches_backend(openapi: dict[str, Any]) -> None:
    """The settings feature validates /ready with zod; its enums must equal the backend's."""
    source = (REPO / "frontend/src/features/settings/schemas/system-status.ts").read_text()
    frontend_values = set(re.findall(r"z\.enum\(\[([^\]]+)\]\)", source))
    flatten = {v.strip(" '\"") for group in frontend_values for v in group.split(",")}
    schemas = openapi["components"]["schemas"]
    backend_values = set(schemas["ReadinessResponse"]["properties"]["status"]["enum"]) | set(
        schemas["DependencyStatus"]["properties"]["status"]["enum"]
    )
    assert flatten == backend_values
