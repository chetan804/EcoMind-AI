"""Analytics endpoints, mounted at ``/api/v1/analytics``. Read-only; needs ``analytics:read``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.modules.analytics import service
from app.modules.analytics.schemas import Overview, WeeklyTrend
from app.modules.auth.dependencies import Principal, require_permissions

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("analytics:read"))]


@router.get("/overview", response_model=Overview)
def overview(
    db: DbSession,
    _: CanRead,
    window_days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> Overview:
    """Operational snapshot. Flow figures use the window; stock figures are current."""
    return service.overview(db, window_days=window_days)


@router.get("/weekly-trend", response_model=WeeklyTrend)
def weekly_trend(
    db: DbSession,
    _: CanRead,
    weeks: Annotated[int, Query(ge=1, le=104)] = 12,
) -> WeeklyTrend:
    return service.weekly_trend(db, weeks=weeks)
