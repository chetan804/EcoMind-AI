"""Material recovery records and their verification. Owned by ``circular_economy``.

Only records with ``verification_status = 'verified'`` count towards recovery metrics.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import CheckConstraint, DateTime, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.circular_economy.constants import RecoveryMethod, VerificationStatus


class RecoveryRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recovery_records"
    __table_args__ = (
        CheckConstraint("input_weight_kg > 0", name="input_weight_positive"),
        CheckConstraint(
            "recovered_weight_kg >= 0 AND recovered_weight_kg <= input_weight_kg",
            name="recovered_within_input",
        ),
        CheckConstraint(
            "(verification_status = 'pending') = (verified_at IS NULL)",
            name="verification_timestamp_consistent",
        ),
        CheckConstraint(
            "(verification_status = 'pending') = (verified_by_id IS NULL)",
            name="verifier_consistent",
        ),
    )

    facility_id: Mapped[uuid.UUID] = fk_uuid("facilities.id")
    material_category_id: Mapped[uuid.UUID] = fk_uuid("material_categories.id")
    collection_task_id: Mapped[uuid.UUID | None] = fk_uuid("collection_tasks.id", nullable=True)
    evidence_media_asset_id: Mapped[uuid.UUID | None] = fk_uuid("media_assets.id", nullable=True)
    recovery_method: Mapped[RecoveryMethod] = mapped_column(
        enum_column(RecoveryMethod), nullable=False
    )
    input_weight_kg: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    recovered_weight_kg: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    processed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    verification_status: Mapped[VerificationStatus] = mapped_column(
        enum_column(VerificationStatus),
        nullable=False,
        index=True,
        server_default=VerificationStatus.PENDING.value,
    )
    verified_by_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
