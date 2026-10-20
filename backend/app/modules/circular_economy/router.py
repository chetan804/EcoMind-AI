"""Recovery-record endpoints, mounted at ``/api/v1/circular-economy``."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.circular_economy import service
from app.modules.circular_economy.constants import RecoveryMethod, VerificationStatus
from app.modules.circular_economy.schemas import (
    RecoveryCreate,
    RecoveryOut,
    RecoverySummary,
    SortField,
    VerifyRequest,
)

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("circular_economy:read"))]
CanManage = Annotated[Principal, Depends(require_permissions("circular_economy:manage"))]
CanVerify = Annotated[Principal, Depends(require_permissions("circular_economy:verify"))]
Pagination = Annotated[PageParams, Depends(page_params)]


@router.get("/recovery-records", response_model=Page[RecoveryOut])
def list_records(
    db: DbSession,
    _: CanRead,
    params: Pagination,
    facility_id: uuid.UUID | None = None,
    material_category_id: uuid.UUID | None = None,
    recovery_method: RecoveryMethod | None = None,
    status_filter: Annotated[VerificationStatus | None, Query(alias="status")] = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    sort_by: SortField = "processed_at",
    order: SortOrder = SortOrder.DESC,
) -> Page[RecoveryOut]:
    return service.list_records(
        db,
        params,
        facility_id=facility_id,
        category_id=material_category_id,
        method=recovery_method,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order=order,
    )


@router.post("/recovery-records", response_model=RecoveryOut, status_code=status.HTTP_201_CREATED)
def create_record(
    payload: RecoveryCreate, request: Request, db: DbSession, principal: CanManage
) -> RecoveryOut:
    """Record processed material; it stays `pending` (uncounted) until someone else verifies it."""
    return service.create(db, principal, payload, context=RequestContext.from_request(request))


@router.get("/recovery-records/summary", response_model=RecoverySummary)
def summary(
    db: DbSession,
    _: CanRead,
    facility_id: uuid.UUID | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> RecoverySummary:
    return service.summary(db, facility_id=facility_id, date_from=date_from, date_to=date_to)


@router.get("/recovery-records/{record_id}", response_model=RecoveryOut)
def get_record(record_id: uuid.UUID, db: DbSession, _: CanRead) -> RecoveryOut:
    return service.get(db, record_id)


@router.post("/recovery-records/{record_id}/verify", response_model=RecoveryOut)
def verify_record(
    record_id: uuid.UUID,
    payload: VerifyRequest,
    request: Request,
    db: DbSession,
    principal: CanVerify,
) -> RecoveryOut:
    """Verify or reject a pending record. The author cannot decide on their own record."""
    return service.decide(
        db, principal, record_id, payload, context=RequestContext.from_request(request)
    )
