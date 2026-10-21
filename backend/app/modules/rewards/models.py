"""Rewards and impact ledger. Owned by the ``rewards`` module.

The ledger is append-only: corrections are new ``reversal``/``adjustment`` rows. A user's balance
is the sum of ``points``. ``source_id`` is a polymorphic reference without a foreign key (it can
point at several tables); uniqueness on (user, source, entry type) makes awards idempotent.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    fk_uuid,
)
from app.modules.rewards.constants import LedgerEntryType, LedgerSourceType, RedemptionStatus

CODE_COLUMN_LENGTH = 16


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


class RewardItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Something a citizen can spend points on. Entered by staff: the platform ships none."""

    __tablename__ = "reward_items"
    __table_args__ = (
        CheckConstraint("points_cost > 0", name="cost_positive"),
        CheckConstraint("stock IS NULL OR stock >= 0", name="stock_non_negative"),
        CheckConstraint("max_per_user IS NULL OR max_per_user >= 1", name="limit_positive"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    points_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL means unlimited. Decremented on redemption, restored on cancellation.
    stock: Mapped[int | None] = mapped_column(Integer)
    max_per_user: Mapped[int | None] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), index=True
    )
    valid_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")


class RewardRedemption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One spend of points on a reward item.

    The ledger holds the money side (a negative ``redeemed`` entry, and a positive ``reversal`` on
    cancellation); this row holds the hand-over side. ``item_name`` and ``points_spent`` are copies,
    so editing the catalogue never rewrites history.
    """

    __tablename__ = "reward_redemptions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "client_request_id", name="uq_reward_redemptions_user_client_request"
        ),
        CheckConstraint("points_spent > 0", name="points_positive"),
        CheckConstraint(
            "(status = 'fulfilled') = (fulfilled_at IS NOT NULL)",
            name="fulfilled_timestamp_consistent",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="cancelled_timestamp_consistent",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (refund_entry_id IS NOT NULL)",
            name="refund_iff_cancelled",
        ),
    )

    user_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    item_id: Mapped[uuid.UUID] = fk_uuid("reward_items.id")
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    points_spent: Mapped[int] = mapped_column(Integer, nullable=False)
    # Shown to the citizen and quoted to staff when the reward is handed over.
    code: Mapped[str] = mapped_column(String(CODE_COLUMN_LENGTH), nullable=False, unique=True)
    # Chosen by the client for each attempt: repeating a request cannot spend points twice.
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[RedemptionStatus] = mapped_column(
        enum_column(RedemptionStatus),
        nullable=False,
        index=True,
        server_default=RedemptionStatus.PENDING.value,
    )
    ledger_entry_id: Mapped[uuid.UUID] = fk_uuid("reward_ledger_entries.id", unique=True)
    refund_entry_id: Mapped[uuid.UUID | None] = fk_uuid(
        "reward_ledger_entries.id", nullable=True, unique=True
    )
    fulfilled_by_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    fulfilled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(500))
    cancelled_by_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(500))
