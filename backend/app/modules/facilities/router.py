"""Facility endpoints, mounted at ``/api/v1/facilities``."""

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
from app.modules.facilities.constants import FacilityStatus, FacilityType
from app.modules.facilities.schemas import (
    FacilityCreate,
    FacilityOut,
    FacilityUpdate,
    SortField,
)

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("facilities:read"))]
CanManage = Annotated[Principal, Depends(require_permissions("facilities:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


@router.get("", response_model=Page[FacilityOut])
def list_facilities(
    db: DbSession,
    principal: CanRead,
    params: Pagination,
    facility_type: FacilityType | None = None,
    status_filter: Annotated[FacilityStatus | None, Query(alias="status")] = None,
    city: Annotated[str | None, Query(max_length=120)] = None,
    q: Annotated[str | None, Query(max_length=100, description="Search name, code, city")] = None,
    sort_by: SortField = "name",
    order: SortOrder = SortOrder.ASC,
) -> Page[FacilityOut]:
    return service.list_facilities(
        db,
        principal,
        params,
        facility_type=facility_type,
        status=status_filter,
        city=city,
        q=q,
        sort_by=sort_by,
        order=order,
    )


@router.post("", response_model=FacilityOut, status_code=status.HTTP_201_CREATED)
def create_facility(
    payload: FacilityCreate, request: Request, db: DbSession, principal: CanManage
) -> FacilityOut:
    return service.create_facility(
        db, principal, payload, context=RequestContext.from_request(request)
    )


@router.get("/{facility_id}", response_model=FacilityOut)
def get_facility(facility_id: uuid.UUID, db: DbSession, principal: CanRead) -> FacilityOut:
    return service.get_facility(db, principal, facility_id)


@router.patch("/{facility_id}", response_model=FacilityOut)
def update_facility(
    facility_id: uuid.UUID,
    payload: FacilityUpdate,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> FacilityOut:
    """Partial update. A facility is deactivated with ``{"status": "inactive"}``, never deleted,
    so collection history that points at it stays intact."""
    return service.update_facility(
        db, principal, facility_id, payload, context=RequestContext.from_request(request)
    )
