"""Administration endpoints, mounted at ``/api/v1/admin``."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import AppSettings, DbSession
from app.common.pagination import Page, PageParams, page_params
from app.modules.administration import service
from app.modules.administration.schemas import (
    AuditEntryOut,
    ReasonRequest,
    RoleOut,
    RolesRequest,
    SystemInfo,
    UserAdminOut,
)
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions

router = APIRouter()

CanReadUsers = Annotated[Principal, Depends(require_permissions("users:read"))]
CanManageUsers = Annotated[Principal, Depends(require_permissions("users:manage"))]
CanReadAudit = Annotated[Principal, Depends(require_permissions("audit:read"))]
CanSettings = Annotated[Principal, Depends(require_permissions("settings:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


@router.get("/users", response_model=Page[UserAdminOut])
def list_users(
    db: DbSession,
    _: CanReadUsers,
    params: Pagination,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: Annotated[str | None, Query(max_length=64)] = None,
    is_active: bool | None = None,
) -> Page[UserAdminOut]:
    return service.list_users(db, params, q=q, role=role, is_active=is_active)


@router.get("/users/{user_id}", response_model=UserAdminOut)
def get_user(user_id: uuid.UUID, db: DbSession, _: CanReadUsers) -> UserAdminOut:
    return service.get_user(db, user_id)


@router.put("/users/{user_id}/roles", response_model=UserAdminOut)
def set_roles(
    user_id: uuid.UUID,
    payload: RolesRequest,
    request: Request,
    db: DbSession,
    principal: CanManageUsers,
) -> UserAdminOut:
    return service.set_roles(
        db, principal, user_id, payload, context=RequestContext.from_request(request)
    )


@router.post("/users/{user_id}/deactivate", response_model=UserAdminOut)
def deactivate(
    user_id: uuid.UUID,
    payload: ReasonRequest,
    request: Request,
    db: DbSession,
    principal: CanManageUsers,
) -> UserAdminOut:
    return service.set_active(
        db,
        principal,
        user_id,
        active=False,
        reason=payload.reason,
        context=RequestContext.from_request(request),
    )


@router.post("/users/{user_id}/activate", response_model=UserAdminOut)
def activate(
    user_id: uuid.UUID,
    payload: ReasonRequest,
    request: Request,
    db: DbSession,
    principal: CanManageUsers,
) -> UserAdminOut:
    return service.set_active(
        db,
        principal,
        user_id,
        active=True,
        reason=payload.reason,
        context=RequestContext.from_request(request),
    )


@router.post("/users/{user_id}/reset-mfa", response_model=UserAdminOut)
def reset_mfa(
    user_id: uuid.UUID,
    payload: ReasonRequest,
    request: Request,
    db: DbSession,
    principal: CanManageUsers,
) -> UserAdminOut:
    """Remove a user's authenticator when they lost both the device and the recovery codes."""
    return service.reset_mfa(
        db,
        principal,
        user_id,
        reason=payload.reason,
        context=RequestContext.from_request(request),
    )


@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: DbSession, _: CanReadUsers) -> list[RoleOut]:
    return service.list_roles(db)


@router.get("/audit-logs", response_model=Page[AuditEntryOut])
def list_audit(
    db: DbSession,
    _: CanReadAudit,
    params: Pagination,
    action: Annotated[str | None, Query(max_length=100)] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    occurred_from: dt.datetime | None = None,
    occurred_to: dt.datetime | None = None,
) -> Page[AuditEntryOut]:
    return service.list_audit(
        db,
        params,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )


@router.get("/system", response_model=SystemInfo)
def system_info(db: DbSession, settings: AppSettings, _: CanSettings) -> SystemInfo:
    return service.system_info(db, settings)
