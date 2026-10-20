"""Material-passport endpoints, mounted at ``/api/v1/material-passports``."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.material_passports import service
from app.modules.material_passports.constants import PassportStatus
from app.modules.material_passports.schemas import (
    EventCreate,
    Integrity,
    LinkRecovery,
    PassportCreate,
    PassportDetail,
    PassportOut,
    SortField,
)

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("passports:read"))]
CanManage = Annotated[Principal, Depends(require_permissions("passports:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


def _ctx(request: Request) -> RequestContext:
    return RequestContext.from_request(request)


@router.get("", response_model=Page[PassportOut])
def list_passports(
    db: DbSession,
    _: CanRead,
    params: Pagination,
    status_filter: Annotated[PassportStatus | None, Query(alias="status")] = None,
    material_category_id: uuid.UUID | None = None,
    facility_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Passport code")] = None,
    sort_by: SortField = "created_at",
    order: SortOrder = SortOrder.DESC,
) -> Page[PassportOut]:
    return service.list_passports(
        db,
        params,
        status=status_filter,
        category_id=material_category_id,
        facility_id=facility_id,
        q=q,
        sort_by=sort_by,
        order=order,
    )


@router.post("", response_model=PassportDetail, status_code=status.HTTP_201_CREATED)
def create_passport(
    payload: PassportCreate, request: Request, db: DbSession, principal: CanManage
) -> PassportDetail:
    """Create a passport; the first custody event (`created`) is written automatically."""
    return service.create(db, principal, payload, context=_ctx(request))


@router.get("/by-code/{code}", response_model=PassportDetail)
def get_by_code(code: str, db: DbSession, _: CanRead) -> PassportDetail:
    return service.get_by_code(db, code)


@router.get("/{passport_id}", response_model=PassportDetail)
def get_passport(passport_id: uuid.UUID, db: DbSession, _: CanRead) -> PassportDetail:
    return service.get(db, passport_id)


@router.post(
    "/{passport_id}/events", response_model=PassportDetail, status_code=status.HTTP_201_CREATED
)
def add_event(
    passport_id: uuid.UUID,
    payload: EventCreate,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> PassportDetail:
    """Append a custody event. Events cannot be edited or deleted."""
    return service.add_event(db, principal, passport_id, payload, context=_ctx(request))


@router.post("/{passport_id}/recovery", response_model=PassportDetail)
def link_recovery(
    passport_id: uuid.UUID,
    payload: LinkRecovery,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> PassportDetail:
    return service.link_recovery(db, principal, passport_id, payload, context=_ctx(request))


@router.get("/{passport_id}/integrity", response_model=Integrity)
def integrity(passport_id: uuid.UUID, db: DbSession, _: CanRead) -> Integrity:
    return service.integrity(db, passport_id)
