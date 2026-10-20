"""Route-planning endpoints, mounted at ``/api/v1/route-planning``."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import AppSettings, DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.integrations.mapping.base import RoadRouteProvider
from app.integrations.mapping.google_routes import GoogleRoutesProvider
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.route_planning import service
from app.modules.route_planning.constants import RoutePlanStatus
from app.modules.route_planning.schemas import (
    PlanCreate,
    PlanDetail,
    PlanOut,
    RoadRouteOut,
    SortField,
    TransitionRequest,
)

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("routes:read"))]
CanManage = Annotated[Principal, Depends(require_permissions("routes:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


def get_road_route_provider(settings: AppSettings) -> RoadRouteProvider:
    """Routing provider for this request. Tests replace it through ``dependency_overrides``."""
    return GoogleRoutesProvider(
        settings.google_maps_server_api_key,
        timeout_seconds=settings.google_routes_timeout_seconds,
    )


RoadRouting = Annotated[RoadRouteProvider, Depends(get_road_route_provider)]


def _ctx(request: Request) -> RequestContext:
    return RequestContext.from_request(request)


@router.get("/plans", response_model=Page[PlanOut])
def list_plans(
    db: DbSession,
    _: CanRead,
    params: Pagination,
    status_filter: Annotated[RoutePlanStatus | None, Query(alias="status")] = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    sort_by: SortField = "planned_date",
    order: SortOrder = SortOrder.DESC,
) -> Page[PlanOut]:
    return service.list_plans(
        db,
        params,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order=order,
    )


@router.post("/plans", response_model=PlanDetail, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreate, request: Request, db: DbSession, principal: CanManage
) -> PlanDetail:
    """Order the given collection tasks for one vehicle and store the proposal as a draft."""
    return service.create_plan(db, principal, payload, context=_ctx(request))


@router.get("/plans/{plan_id}", response_model=PlanDetail)
def get_plan(plan_id: uuid.UUID, db: DbSession, _: CanRead) -> PlanDetail:
    return service.get_plan(db, plan_id)


@router.get("/plans/{plan_id}/road-route", response_model=RoadRouteOut)
def get_road_route(
    plan_id: uuid.UUID, db: DbSession, _: CanRead, provider: RoadRouting
) -> RoadRouteOut:
    """Road geometry, distance and duration from the routing provider (never stored).

    Answers 200 with ``available: false`` and a reason when the provider is not configured or
    fails, so the client can show a labelled straight-line fallback."""
    return service.road_route(db, plan_id, provider)


@router.post("/plans/{plan_id}/publish", response_model=PlanDetail)
def publish_plan(
    plan_id: uuid.UUID,
    payload: TransitionRequest,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> PlanDetail:
    return service.transition(
        db, principal, plan_id, RoutePlanStatus.PUBLISHED, payload.reason, context=_ctx(request)
    )


@router.post("/plans/{plan_id}/cancel", response_model=PlanDetail)
def cancel_plan(
    plan_id: uuid.UUID,
    payload: TransitionRequest,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> PlanDetail:
    return service.transition(
        db, principal, plan_id, RoutePlanStatus.CANCELLED, payload.reason, context=_ctx(request)
    )
