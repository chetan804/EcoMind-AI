"""Rewards and impact ledger endpoints, mounted at ``/api/v1/rewards``."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import AppSettings, DbSession
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.rewards import adjustments, service
from app.modules.rewards.constants import LedgerEntryType, LedgerSourceType
from app.modules.rewards.models import RewardLedgerEntry
from app.modules.rewards.schemas import (
    AdjustmentCreate,
    Balance,
    EntryOut,
    LedgerSummary,
    ReverseRequest,
)

router = APIRouter()

Own = Annotated[Principal, Depends(require_permissions("rewards:read_own"))]
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
