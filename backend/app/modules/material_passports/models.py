"""Material passports and chain-of-custody events. Owned by ``material_passports``."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    fk_uuid,
)
from app.modules.material_passports.constants import CustodyEventType, PassportStatus


class MaterialPassport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "material_passports"
    __table_args__ = (CheckConstraint("weight_kg > 0", name="weight_positive"),)

    passport_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    material_category_id: Mapped[uuid.UUID] = fk_uuid("material_categories.id")
    status: Mapped[PassportStatus] = mapped_column(
        enum_column(PassportStatus),
        nullable=False,
        index=True,
        server_default=PassportStatus.ACTIVE.value,
    )
    description: Mapped[str | None] = mapped_column(Text)
    weight_kg: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    origin_collection_task_id: Mapped[uuid.UUID | None] = fk_uuid(
        "collection_tasks.id", nullable=True
    )
    recovery_record_id: Mapped[uuid.UUID | None] = fk_uuid("recovery_records.id", nullable=True)
    current_facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    created_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")


class CustodyEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only chain-of-custody entry; ``sequence`` orders events within a passport."""

    __tablename__ = "custody_events"
    __table_args__ = (
        UniqueConstraint(
            "material_passport_id",
            "sequence",
            name="uq_custody_events_material_passport_id_sequence",
        ),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
    )

    material_passport_id: Mapped[uuid.UUID] = fk_uuid("material_passports.id", ondelete="CASCADE")
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[CustodyEventType] = mapped_column(
        enum_column(CustodyEventType), nullable=False
    )
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    from_facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    to_facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
