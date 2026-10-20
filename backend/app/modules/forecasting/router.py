"""Forecasting endpoints, mounted at ``/api/v1/forecasting``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import DbSession
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.forecasting import service
from app.modules.forecasting.schemas import (
    ForecastOut,
    ForecastRequest,
    SeriesHistory,
    SeriesInfo,
    StoredForecastOut,
)

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("forecasting:read"))]
CanRun = Annotated[Principal, Depends(require_permissions("forecasting:run"))]
SeriesRef = Annotated[str, Query(min_length=3, max_length=80, alias="series")]


@router.get("/series", response_model=list[SeriesInfo])
def list_series(db: DbSession, _: CanRead) -> list[SeriesInfo]:
    """Series that can be forecast: the platform's own, and clearly labelled public data."""
    return service.list_series(db)


@router.get("/series/history", response_model=SeriesHistory)
def series_history(db: DbSession, _: CanRead, ref: SeriesRef) -> SeriesHistory:
    return service.get_history(db, ref)


@router.post("/forecasts", response_model=ForecastOut, status_code=status.HTTP_201_CREATED)
def run_forecast(
    payload: ForecastRequest, request: Request, db: DbSession, principal: CanRun
) -> ForecastOut:
    """Compute, and by default store, a weekly forecast. ``422 insufficient_history`` when the
    series is too short; nothing is invented."""
    return service.run_forecast(
        db, principal, payload, context=RequestContext.from_request(request)
    )


@router.get("/forecasts/latest", response_model=StoredForecastOut)
def latest_forecast(db: DbSession, _: CanRead, ref: SeriesRef) -> StoredForecastOut:
    return service.latest_stored(db, ref)
