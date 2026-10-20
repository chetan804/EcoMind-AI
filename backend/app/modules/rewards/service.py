"""Rewards and impact ledger writes. The caller owns the transaction (no commit here).

Policy (documented in docs/api/collections-api.md): a reporter earns
``round(weight_kg * REWARD_POINTS_PER_KG)`` points (at least 1 when the weight is positive and
the rate is non-zero) when a collection task created from their VERIFIED report is completed
with a recorded weight. The entry is append-only and idempotent per (user, task).
"""

from __future__ import annotations

import decimal
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

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
