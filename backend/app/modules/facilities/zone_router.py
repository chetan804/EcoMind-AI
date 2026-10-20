"""Zone endpoints, mounted at ``/api/v1/zones``. Same permissions as facilities."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.facilities import service
from app.modules.facilities.constants import ZoneType
from app.modules.facilities.schemas import ZoneCreate, ZoneOut, ZoneSortField, ZoneUpdate

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("facilities:read"))]
CanManage = Annotated[Principal, Depends(require_permissions("facilities:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


@router.get("", response_model=Page[ZoneOut])
def list_zones(
    db: DbSession,
    principal: CanRead,
    params: Pagination,
    zone_type: ZoneType | None = None,
    active: bool | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Search name or code")] = None,
    sort_by: ZoneSortField = "name",
    order: SortOrder = SortOrder.ASC,
) -> Page[ZoneOut]:
    return service.list_zones(
        db, params, zone_type=zone_type, active=active, q=q, sort_by=sort_by, order=order
    )


@router.post("", response_model=ZoneOut, status_code=status.HTTP_201_CREATED)
def create_zone(
    payload: ZoneCreate, request: Request, db: DbSession, principal: CanManage
) -> ZoneOut:
    return service.create_zone(db, principal, payload, context=RequestContext.from_request(request))


@router.get("/{zone_id}", response_model=ZoneOut)
def get_zone(zone_id: uuid.UUID, db: DbSession, principal: CanRead) -> ZoneOut:
    return service.get_zone(db, zone_id)


@router.patch("/{zone_id}", response_model=ZoneOut)
def update_zone(
    zone_id: uuid.UUID,
    payload: ZoneUpdate,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> ZoneOut:
    """Partial update. A zone is retired with ``{"is_active": false}``, never deleted."""
    return service.update_zone(
        db, principal, zone_id, payload, context=RequestContext.from_request(request)
    )
