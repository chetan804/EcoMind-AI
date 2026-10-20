"""Rewards and impact ledger writes. The caller owns the transaction (no commit here).

Policy (documented in docs/api/collections-api.md): a reporter earns
``round(weight_kg * REWARD_POINTS_PER_KG)`` points (at least 1 when the weight is positive and
the rate is non-zero) when a collection task created from their VERIFIED report is completed
with a recorded weight. The entry is append-only and idempotent per (user, task).
"""

from __future__ import annotations

import decimal
import uuid

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.rewards.constants import LedgerEntryType, LedgerSourceType
from app.modules.rewards.models import RewardLedgerEntry


def points_for_weight(weight_kg: decimal.Decimal, points_per_kg: int) -> int:
    if weight_kg <= 0 or points_per_kg <= 0:
        return 0
    return max(1, int((weight_kg * points_per_kg).quantize(decimal.Decimal(1))))


def award_for_collection(
    db: Session,
    *,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    weight_kg: decimal.Decimal,
    points_per_kg: int,
    created_by_id: uuid.UUID,
) -> RewardLedgerEntry | None:
    """Credit the reporter once per collection task; returns ``None`` when nothing is due."""
    points = points_for_weight(weight_kg, points_per_kg)
    if points == 0:
        return None
    existing = db.scalar(
        select(RewardLedgerEntry).where(
            RewardLedgerEntry.user_id == user_id,
            RewardLedgerEntry.source_type == LedgerSourceType.COLLECTION_TASK,
            RewardLedgerEntry.source_id == task_id,
            RewardLedgerEntry.entry_type == LedgerEntryType.EARNED,
        )
    )
    if existing is not None:
        return existing
    entry = RewardLedgerEntry(
        user_id=user_id,
        entry_type=LedgerEntryType.EARNED,
        points=points,
        impact_weight_kg=weight_kg,
        source_type=LedgerSourceType.COLLECTION_TASK,
        source_id=task_id,
        created_by_id=created_by_id,
        description="Waste collected from your report",
    )
    db.add(entry)
    db.flush()
    return entry


# ----------------------------------------------------------------------------- read models


def balance_of(db: Session, user_id: uuid.UUID) -> tuple[int, int, decimal.Decimal, int]:
    """(net points, earned points, net impact kg, entries) for one user."""
    impact = case(
        (
            RewardLedgerEntry.entry_type == LedgerEntryType.EARNED,
            RewardLedgerEntry.impact_weight_kg,
        ),
        (
            RewardLedgerEntry.entry_type == LedgerEntryType.REVERSAL,
            -RewardLedgerEntry.impact_weight_kg,
        ),
        else_=0,
    )
    earned = case(
        (RewardLedgerEntry.entry_type == LedgerEntryType.EARNED, RewardLedgerEntry.points), else_=0
    )
    row = db.execute(
        select(
            func.coalesce(func.sum(RewardLedgerEntry.points), 0),
            func.coalesce(func.sum(earned), 0),
            func.coalesce(func.sum(func.coalesce(impact, 0)), 0),
            func.count(),
        ).where(RewardLedgerEntry.user_id == user_id)
    ).one()
    return int(row[0]), int(row[1]), decimal.Decimal(row[2]), int(row[3])


def entries_page(
    db: Session,
    params: PageParams,
    *,
    user_id: uuid.UUID | None,
    entry_type: LedgerEntryType | None,
    source_type: LedgerSourceType | None,
) -> tuple[list[RewardLedgerEntry], int]:
    stmt = select(RewardLedgerEntry)
    if user_id is not None:
        stmt = stmt.where(RewardLedgerEntry.user_id == user_id)
    if entry_type is not None:
        stmt = stmt.where(RewardLedgerEntry.entry_type == entry_type)
    if source_type is not None:
        stmt = stmt.where(RewardLedgerEntry.source_type == source_type)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(RewardLedgerEntry.created_at.desc(), RewardLedgerEntry.id)
        .offset(params.offset)
        .limit(params.limit)
    ).scalars()
    return list(rows), int(total)


def summary(db: Session) -> tuple[int, int, int, int, decimal.Decimal]:
    """(entries, users, issued, removed, net impact kg) across the ledger."""
    impact = case(
        (
            RewardLedgerEntry.entry_type == LedgerEntryType.EARNED,
            RewardLedgerEntry.impact_weight_kg,
        ),
        (
            RewardLedgerEntry.entry_type == LedgerEntryType.REVERSAL,
            -RewardLedgerEntry.impact_weight_kg,
        ),
        else_=0,
    )
    positive = case((RewardLedgerEntry.points > 0, RewardLedgerEntry.points), else_=0)
    negative = case((RewardLedgerEntry.points < 0, -RewardLedgerEntry.points), else_=0)
    row = db.execute(
        select(
            func.count(),
            func.count(func.distinct(RewardLedgerEntry.user_id)),
            func.coalesce(func.sum(positive), 0),
            func.coalesce(func.sum(negative), 0),
            func.coalesce(func.sum(func.coalesce(impact, 0)), 0),
        )
    ).one()
    return int(row[0]), int(row[1]), int(row[2]), int(row[3]), decimal.Decimal(row[4])


def get_entry(db: Session, entry_id: uuid.UUID) -> RewardLedgerEntry | None:
    return db.get(RewardLedgerEntry, entry_id)


def reversal_of(db: Session, entry_id: uuid.UUID) -> RewardLedgerEntry | None:
    return db.scalar(
        select(RewardLedgerEntry).where(RewardLedgerEntry.reverses_entry_id == entry_id)
    )


def append(db: Session, **fields: object) -> RewardLedgerEntry:
    entry = RewardLedgerEntry(**fields)
    db.add(entry)
    db.flush()
    return entry
