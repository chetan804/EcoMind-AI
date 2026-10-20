"""Fleet endpoints, mounted at ``/api/v1/fleet``."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.fleet import service
from app.modules.fleet.constants import VehicleStatus, VehicleType
from app.modules.fleet.schemas import SortField, VehicleCreate, VehicleOut, VehicleUpdate

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("fleet:read"))]
CanManage = Annotated[Principal, Depends(require_permissions("fleet:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


@router.get("/vehicles", response_model=Page[VehicleOut])
def list_vehicles(
    db: DbSession,
    _: CanRead,
    params: Pagination,
    vehicle_type: VehicleType | None = None,
    status_filter: Annotated[VehicleStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=40, description="Search registration")] = None,
    sort_by: SortField = "registration_number",
    order: SortOrder = SortOrder.ASC,
) -> Page[VehicleOut]:
    return service.list_vehicles(
        db,
        params,
        vehicle_type=vehicle_type,
        status=status_filter,
        q=q,
        sort_by=sort_by,
        order=order,
    )


@router.post("/vehicles", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    payload: VehicleCreate, request: Request, db: DbSession, principal: CanManage
) -> VehicleOut:
    return service.create_vehicle(
        db, principal, payload, context=RequestContext.from_request(request)
    )


@router.get("/vehicles/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(vehicle_id: uuid.UUID, db: DbSession, _: CanRead) -> VehicleOut:
    return service.get_vehicle(db, vehicle_id)


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(
    vehicle_id: uuid.UUID,
    payload: VehicleUpdate,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> VehicleOut:
    """Partial update. Vehicles are retired with ``{"status": "retired"}``, never deleted, so
    collection history that points at them stays intact."""
    return service.update_vehicle(
        db, principal, vehicle_id, payload, context=RequestContext.from_request(request)
    )
