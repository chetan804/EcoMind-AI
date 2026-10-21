"""Rewards and impact ledger endpoints, mounted at ``/api/v1/rewards``."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Response, status

from app.api.deps import AppSettings, DbSession
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.rewards import adjustments, catalog, service
from app.modules.rewards.constants import LedgerEntryType, LedgerSourceType, RedemptionStatus
from app.modules.rewards.models import RewardLedgerEntry
from app.modules.rewards.schemas import (
    AdjustmentCreate,
    Balance,
    CancelOwnRequest,
    CatalogItemOut,
    EntryOut,
    FulfilRequest,
    ItemCreate,
    ItemOut,
    ItemUpdate,
    LedgerSummary,
    RedeemRequest,
    RedemptionOut,
    ReverseRequest,
)

router = APIRouter()

Own = Annotated[Principal, Depends(require_permissions("rewards:read_own"))]
Redeem = Annotated[Principal, Depends(require_permissions("rewards:redeem"))]
Manage = Annotated[Principal, Depends(require_permissions("rewards:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


def _entries(rows: Sequence[RewardLedgerEntry], total: int, params: PageParams) -> Page[EntryOut]:
    return Page.build(
        [EntryOut.model_validate(r, from_attributes=True) for r in rows], total, params
    )


@router.get("/me/balance", response_model=Balance)
def my_balance(db: DbSession, principal: Own, settings: AppSettings) -> Balance:
    points, earned, impact, count = service.balance_of(db, principal.user_id)
    return Balance(
        user_id=principal.user_id,
        points=points,
        earned_points=earned,
        impact_weight_kg=impact,
        entries=count,
        points_per_kg=settings.reward_points_per_kg,
    )


@router.get("/me/entries", response_model=Page[EntryOut])
def my_entries(
    db: DbSession,
    principal: Own,
    params: Pagination,
    entry_type: LedgerEntryType | None = None,
) -> Page[EntryOut]:
    rows, total = service.entries_page(
        db, params, user_id=principal.user_id, entry_type=entry_type, source_type=None
    )
    return _entries(rows, total, params)


@router.get("/ledger", response_model=Page[EntryOut])
def ledger(
    db: DbSession,
    _: Manage,
    params: Pagination,
    user_id: uuid.UUID | None = None,
    entry_type: LedgerEntryType | None = None,
    source_type: LedgerSourceType | None = None,
) -> Page[EntryOut]:
    rows, total = service.entries_page(
        db, params, user_id=user_id, entry_type=entry_type, source_type=source_type
    )
    return _entries(rows, total, params)


@router.get("/ledger/summary", response_model=LedgerSummary)
def ledger_summary(db: DbSession, _: Manage) -> LedgerSummary:
    entries, users, issued, removed, impact = service.summary(db)
    return LedgerSummary(
        entries=entries,
        users=users,
        points_issued=issued,
        points_removed=removed,
        net_points=issued - removed,
        impact_weight_kg=impact,
    )


@router.post("/adjustments", response_model=EntryOut, status_code=status.HTTP_201_CREATED)
def create_adjustment(
    payload: AdjustmentCreate, request: Request, db: DbSession, principal: Manage
) -> EntryOut:
    entry = adjustments.adjust(db, principal, payload, context=RequestContext.from_request(request))
    return EntryOut.model_validate(entry, from_attributes=True)


@router.post(
    "/entries/{entry_id}/reverse", response_model=EntryOut, status_code=status.HTTP_201_CREATED
)
def reverse_entry(
    entry_id: uuid.UUID,
    payload: ReverseRequest,
    request: Request,
    db: DbSession,
    principal: Manage,
) -> EntryOut:
    entry = adjustments.reverse(
        db, principal, entry_id, payload, context=RequestContext.from_request(request)
    )
    return EntryOut.model_validate(entry, from_attributes=True)


# -- catalogue and redemptions -------------------------------------------------------------------
@router.get("/catalog", response_model=Page[CatalogItemOut])
def browse_catalog(db: DbSession, principal: Own, params: Pagination) -> Page[CatalogItemOut]:
    """What the caller can spend points on: active, unexpired items (out-of-stock ones marked)."""
    return catalog.catalog_for(db, principal, params)


@router.post("/catalog/{item_id}/redeem", response_model=RedemptionOut)
def redeem_item(
    item_id: uuid.UUID,
    payload: RedeemRequest,
    request: Request,
    response: Response,
    db: DbSession,
    principal: Redeem,
) -> RedemptionOut:
    """Spend points. `201` when new; `200` with the same body when `client_request_id` repeats."""
    out, created = catalog.redeem(
        db, principal, item_id, payload, context=RequestContext.from_request(request)
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return out


@router.get("/me/redemptions", response_model=Page[RedemptionOut])
def my_redemptions(db: DbSession, principal: Own, params: Pagination) -> Page[RedemptionOut]:
    return catalog.my_redemptions(db, principal, params)


@router.post("/me/redemptions/{redemption_id}/cancel", response_model=RedemptionOut)
def cancel_my_redemption(
    redemption_id: uuid.UUID,
    request: Request,
    db: DbSession,
    principal: Redeem,
    payload: Annotated[CancelOwnRequest, Body(default_factory=CancelOwnRequest)],
) -> RedemptionOut:
    """Cancel your own pending redemption; the points come back."""
    return catalog.cancel_own(
        db, principal, redemption_id, payload, context=RequestContext.from_request(request)
    )


@router.get("/items", response_model=Page[ItemOut])
def list_items(
    db: DbSession, _: Manage, params: Pagination, active: bool | None = None
) -> Page[ItemOut]:
    return catalog.list_items(db, params, active=active)


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, request: Request, db: DbSession, principal: Manage) -> ItemOut:
    return catalog.create_item(db, principal, payload, context=RequestContext.from_request(request))


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    request: Request,
    db: DbSession,
    principal: Manage,
) -> ItemOut:
    return catalog.update_item(
        db, principal, item_id, payload, context=RequestContext.from_request(request)
    )


@router.get("/redemptions", response_model=Page[RedemptionOut])
def list_redemptions(
    db: DbSession,
    _: Manage,
    params: Pagination,
    status: RedemptionStatus | None = None,
    code: str | None = None,
    user_id: uuid.UUID | None = None,
) -> Page[RedemptionOut]:
    return catalog.list_redemptions(db, params, status=status, code=code, user_id=user_id)


@router.post("/redemptions/{redemption_id}/fulfil", response_model=RedemptionOut)
def fulfil_redemption(
    redemption_id: uuid.UUID,
    request: Request,
    db: DbSession,
    principal: Manage,
    payload: Annotated[FulfilRequest, Body(default_factory=FulfilRequest)],
) -> RedemptionOut:
    """Staff: the reward was handed over."""
    return catalog.fulfil(
        db, principal, redemption_id, payload, context=RequestContext.from_request(request)
    )


@router.post("/redemptions/{redemption_id}/cancel", response_model=RedemptionOut)
def cancel_redemption(
    redemption_id: uuid.UUID,
    payload: ReverseRequest,
    request: Request,
    db: DbSession,
    principal: Manage,
) -> RedemptionOut:
    """Staff: cancel a pending redemption with a reason; the points and stock come back."""
    return catalog.cancel(
        db,
        principal,
        redemption_id,
        payload.reason,
        by_owner=False,
        context=RequestContext.from_request(request),
    )
