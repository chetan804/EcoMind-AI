"""Vehicle tracking endpoints, mounted at ``/api/v1/tracking``."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import AppSettings, DbSession
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_any_permission, require_permissions
from app.modules.tracking import service
from app.modules.tracking.constants import LocationSource
from app.modules.tracking.schemas import (
    CollectionTracking,
    IngestResult,
    LatestPositions,
    LocationOut,
    LocationReport,
    RouteTracking,
    SimulatedLocation,
    TrackingConfig,
    VehiclePosition,
)

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("fleet:read"))]
CanTrack = Annotated[Principal, Depends(require_permissions("fleet:track"))]
CanReport = Annotated[Principal, Depends(require_any_permission("fleet:track", "fleet:manage"))]
CanSimulate = Annotated[Principal, Depends(require_permissions("fleet:simulate"))]
CanReadCollections = Annotated[Principal, Depends(require_permissions("collection:read"))]
CanReadRoutes = Annotated[Principal, Depends(require_permissions("routes:read"))]
Pagination = Annotated[PageParams, Depends(page_params)]


@router.get("/config", response_model=TrackingConfig)
def get_config(settings: AppSettings, _: CanRead) -> TrackingConfig:
    return service.tracking_config(settings)


@router.get("/vehicles", response_model=LatestPositions)
def latest_positions(
    db: DbSession,
    settings: AppSettings,
    principal: CanRead,
    include_simulated: bool = False,
) -> LatestPositions:
    """Newest position per vehicle with its LIVE / DELAYED / STALE / HISTORICAL / SIMULATED /
    UNAVAILABLE label. Callers without ``fleet:manage`` see only their own assigned vehicles."""
    return service.latest_positions(db, principal, settings, include_simulated=include_simulated)


@router.get("/vehicles/{vehicle_id}", response_model=list[VehiclePosition])
def vehicle_position(
    vehicle_id: uuid.UUID, db: DbSession, settings: AppSettings, principal: CanRead
) -> list[VehiclePosition]:
    return service.vehicle_position(db, principal, settings, vehicle_id)


@router.get("/vehicles/{vehicle_id}/locations", response_model=Page[LocationOut])
def location_history(
    vehicle_id: uuid.UUID,
    db: DbSession,
    principal: CanRead,
    params: Pagination,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
    source: LocationSource | None = None,
    include_simulated: bool = False,
) -> Page[LocationOut]:
    return service.list_history(
        db,
        principal,
        vehicle_id,
        params,
        since=since,
        until=until,
        source=source,
        include_simulated=include_simulated,
    )


@router.post(
    "/vehicles/{vehicle_id}/locations",
    response_model=IngestResult,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "The event was already stored (idempotent retry)"}},
)
def report_location(
    vehicle_id: uuid.UUID,
    payload: LocationReport,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    principal: CanReport,
) -> IngestResult:
    """Post one position. Collectors report for their own vehicle (``fleet:track``); managers
    import past tracks (``source: imported``)."""
    result = service.report_location(
        db,
        principal,
        settings,
        vehicle_id,
        payload,
        context=RequestContext.from_request(request),
    )
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/simulation/vehicles/{vehicle_id}/locations",
    response_model=IngestResult,
    status_code=status.HTTP_201_CREATED,
)
def simulate_location(
    vehicle_id: uuid.UUID,
    payload: SimulatedLocation,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    principal: CanSimulate,
) -> IngestResult:
    """Write a labelled simulator position (source ``simulator``, kept apart from real data)."""
    result = service.simulate_location(db, principal, settings, vehicle_id, payload)
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    return result


@router.delete("/simulation/vehicles/{vehicle_id}/locations", status_code=status.HTTP_200_OK)
def reset_simulation(
    vehicle_id: uuid.UUID,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    principal: CanSimulate,
) -> dict[str, int]:
    """Remove this vehicle's simulator events only. Real events are never touched."""
    removed = service.reset_simulation(
        db, principal, settings, vehicle_id, context=RequestContext.from_request(request)
    )
    return {"removed": removed}


@router.get("/collections/{task_id}", response_model=CollectionTracking)
def collection_tracking(
    task_id: uuid.UUID, db: DbSession, settings: AppSettings, principal: CanReadCollections
) -> CollectionTracking:
    return service.collection_tracking(db, principal, settings, task_id)


@router.get("/route-plans/{plan_id}", response_model=RouteTracking)
def route_tracking(
    plan_id: uuid.UUID,
    db: DbSession,
    settings: AppSettings,
    principal: CanReadRoutes,
    include_simulated: Annotated[bool, Query()] = False,
) -> RouteTracking:
    return service.route_tracking(
        db, principal, settings, plan_id, include_simulated=include_simulated
    )
