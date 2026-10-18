"""Operational endpoints. They live at the root (not under /api/v1) so that orchestrators and
load balancers can probe them without knowing the API version.

- ``GET /health``  liveness: the process is up and serving requests. It checks no dependencies,
  so a database outage never causes a restart loop.
- ``GET /ready``   readiness: the app can serve traffic. Verifies (1) PostgreSQL answers a query
  and (2) the database schema is at the Alembic head revision shipped with this build.
  Returns 503 with the failing checks when not ready. Details never include credentials.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import Engine, inspect, text

from app.common.response_schemas import DependencyStatus, LivenessResponse, ReadinessResponse
from app.db.session import get_engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def expected_migration_head() -> str | None:
    """Head revision of the migration scripts shipped with this build."""
    return ScriptDirectory.from_config(Config(str(_ALEMBIC_INI))).get_current_head()


def run_readiness_checks(engine: Engine) -> dict[str, DependencyStatus]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current: str | None = None
            if inspect(connection).has_table("alembic_version"):
                current = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
    except Exception:
        logger.exception("Readiness: database check failed")
        return {"database": DependencyStatus(status="failed", detail="database unreachable")}

    checks = {"database": DependencyStatus(status="ok")}
    head = expected_migration_head()
    if current == head:
        checks["migrations"] = DependencyStatus(status="ok")
    else:
        checks["migrations"] = DependencyStatus(
            status="failed",
            detail=f"schema revision is {current or 'none'}, expected {head}; "
            "run `alembic upgrade head`",
        )
    return checks


@router.get("/health", response_model=LivenessResponse, summary="Liveness probe")
def health() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={503: {"model": ReadinessResponse, "description": "A dependency is not ready"}},
)
def ready(response: Response, engine: Annotated[Engine, Depends(get_engine)]) -> ReadinessResponse:
    checks = run_readiness_checks(engine)
    is_ready = all(check.status == "ok" for check in checks.values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if is_ready else "not_ready", checks=checks)
