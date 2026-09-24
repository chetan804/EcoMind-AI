"""Citizen sustainability points and the append-only award ledger.

Deliberately *not* a tradable token system: points are engagement recognition
only ("sustainability points"), consistent with docs/PRIVACY.md and the
product decision to avoid financial-instrument semantics (ADR-0009).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class RewardReason(str, enum.Enum):
    signup = "signup"
    report_submitted = "report_submitted"
    report_resolved = "report_resolved"
    complaint_resolved = "complaint_resolved"
    recycling_verified = "recycling_verified"
    achievement = "achievement"


class RewardLedger(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "reward_ledger"

    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False)  # signed
    reason: Mapped[RewardReason] = mapped_column(
        SAEnum(RewardReason, native_enum=False, length=32), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(200))
    reference_type: Mapped[str | None] = mapped_column(String(48))
    reference_id: Mapped[uuid.UUID | None] = mapped_column()
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_reward_ledger_user", "user_id", "awarded_at"),)
