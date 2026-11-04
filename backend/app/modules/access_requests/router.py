"""Role-request endpoints, mounted at ``/api/v1/access-requests``.

The first three routes act only on the caller's own requests. Listing and deciding need
``users:manage`` (administrators only).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import DbSession
from app.common.pagination import Page, PageParams, page_params
from app.modules.access_requests import service
from app.modules.access_requests.constants import RequestableRole, RequestStatus
from app.modules.access_requests.schemas import DecisionRequest, RoleRequestCreate, RoleRequestOut
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import ActivePrincipal, Principal, require_permissions

router = APIRouter()

CanReview = Annotated[Principal, Depends(require_permissions("users:manage"))]
CanDecide = Annotated[Principal, Depends(require_permissions("users:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


def _ctx(request: Request) -> RequestContext:
    return RequestContext.from_request(request)


@router.post("", response_model=RoleRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RoleRequestCreate, request: Request, db: DbSession, principal: ActivePrincipal
) -> RoleRequestOut:
    """Ask an administrator for an operational role. Does not change any role by itself."""
    return service.create(db, principal, payload, context=_ctx(request))


@router.get("/mine", response_model=list[RoleRequestOut])
def my_requests(db: DbSession, principal: ActivePrincipal) -> list[RoleRequestOut]:
    return service.list_mine(db, principal)


@router.post("/{request_id}/withdraw", response_model=RoleRequestOut)
def withdraw_request(
    request_id: uuid.UUID, request: Request, db: DbSession, principal: ActivePrincipal
) -> RoleRequestOut:
    return service.withdraw(db, principal, request_id, context=_ctx(request))


@router.get("", response_model=Page[RoleRequestOut])
def list_requests(
    db: DbSession,
    _: CanReview,
    params: Pagination,
    status_filter: RequestStatus | None = None,
    role: RequestableRole | None = None,
) -> Page[RoleRequestOut]:
    return service.list_all(db, params, status=status_filter, role=role)


@router.post("/{request_id}/decision", response_model=RoleRequestOut)
def decide_request(
    request_id: uuid.UUID,
    payload: DecisionRequest,
    request: Request,
    db: DbSession,
    principal: CanDecide,
) -> RoleRequestOut:
    """Approve (adds the role) or reject (a reason is required); never on your own request."""
    return service.decide(db, principal, request_id, payload, context=_ctx(request))
