"""Rewards and impact ledger. Owned by the ``rewards`` module.

The ledger is append-only: corrections are new ``reversal``/``adjustment`` rows. A user's balance
is the sum of ``points``. ``source_id`` is a polymorphic reference without a foreign key (it can
point at several tables); uniqueness on (user, source, entry type) makes awards idempotent.
"""

from __future__ import annotations

import decimal
import uuid

from sqlalchemy import CheckConstraint, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.rewards.constants import LedgerEntryType, LedgerSourceType


class RewardLedgerEntry(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "reward_ledger_entries"
    __table_args__ = (
        CheckConstraint("points <> 0", name="points_non_zero"),
        CheckConstraint(
            "impact_weight_kg IS NULL OR impact_weight_kg >= 0", name="impact_non_negative"
        ),
        CheckConstraint(
            "(entry_type = 'reversal') = (reverses_entry_id IS NOT NULL)",
            name="reversal_references_entry",
        ),
        Index(
            "uq_reward_ledger_entries_idempotency",
            "user_id",
            "source_type",
            "source_id",
            "entry_type",
            unique=True,
            postgresql_where=text("source_id IS NOT NULL AND entry_type = 'earned'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    entry_type: Mapped[LedgerEntryType] = mapped_column(
        enum_column(LedgerEntryType), nullable=False
    )
    # Signed: positive credits points, negative debits (redemptions, reversals).
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    # Verified waste weight this entry represents, in kilograms (impact ledger).
    impact_weight_kg: Mapped[decimal.Decimal | None] = mapped_column(Numeric(14, 3))
    source_type: Mapped[LedgerSourceType] = mapped_column(
        enum_column(LedgerSourceType), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reverses_entry_id: Mapped[uuid.UUID | None] = fk_uuid("reward_ledger_entries.id", nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    description: Mapped[str | None] = mapped_column(String(500))
