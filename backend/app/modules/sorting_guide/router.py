"""Sorting-guide endpoints, mounted at ``/api/v1/sorting-guide``."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.sorting_guide import service
from app.modules.sorting_guide.constants import DisposalMethod
from app.modules.sorting_guide.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    GuidanceCreate,
    GuidanceOut,
    GuidanceSort,
    GuidanceUpdate,
)

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("sorting_guide:read"))]
CanManage = Annotated[Principal, Depends(require_permissions("sorting_guide:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]
Search = Annotated[str | None, Query(max_length=100)]


def _ctx(request: Request) -> RequestContext:
    return RequestContext.from_request(request)


@router.get("/categories", response_model=Page[CategoryOut])
def list_categories(
    db: DbSession,
    principal: CanRead,
    params: Pagination,
    include_inactive: bool = False,
    q: Search = None,
) -> Page[CategoryOut]:
    """`include_inactive` is honoured only for users who can manage the guide."""
    return service.list_categories(db, principal, params, include_inactive=include_inactive, q=q)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate, request: Request, db: DbSession, principal: CanManage
) -> CategoryOut:
    return service.create_category(db, principal, payload, context=_ctx(request))


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> CategoryOut:
    return service.update_category(db, principal, category_id, payload, context=_ctx(request))


@router.get("/guidance", response_model=Page[GuidanceOut])
def list_guidance(
    db: DbSession,
    principal: CanRead,
    params: Pagination,
    category_id: uuid.UUID | None = None,
    disposal_method: DisposalMethod | None = None,
    include_inactive: bool = False,
    q: Search = None,
    sort_by: GuidanceSort = "title",
    order: SortOrder = SortOrder.ASC,
) -> Page[GuidanceOut]:
    return service.list_guidance(
        db,
        principal,
        params,
        category_id=category_id,
        disposal_method=disposal_method,
        include_inactive=include_inactive,
        q=q,
        sort_by=sort_by,
        order=order,
    )


@router.post("/guidance", response_model=GuidanceOut, status_code=status.HTTP_201_CREATED)
def create_guidance(
    payload: GuidanceCreate, request: Request, db: DbSession, principal: CanManage
) -> GuidanceOut:
    return service.create_guidance(db, principal, payload, context=_ctx(request))


@router.get("/guidance/{guidance_id}", response_model=GuidanceOut)
def get_guidance(guidance_id: uuid.UUID, db: DbSession, principal: CanRead) -> GuidanceOut:
    return service.get_guidance(db, principal, guidance_id)


@router.patch("/guidance/{guidance_id}", response_model=GuidanceOut)
def update_guidance(
    guidance_id: uuid.UUID,
    payload: GuidanceUpdate,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> GuidanceOut:
    return service.update_guidance(db, principal, guidance_id, payload, context=_ctx(request))
