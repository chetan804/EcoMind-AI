"""Vehicle location events. Owned by the ``tracking`` module.

Append-only: rows are never updated (a database trigger enforces it, migration 0011). They are
deleted only by the retention job, which removes whole rows older than the retention period, and
by the simulator reset, which removes ``source = 'simulator'`` rows only.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.tracking.constants import LocationQuality, LocationSource


class VehicleLocationEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "vehicle_location_events"
    __table_args__ = (
        UniqueConstraint(
            "vehicle_id", "source", "recorded_at", name="uq_vehicle_location_events_identity"
        ),
        # A device-supplied sequence number is an idempotency key as well.
        Index(
            "uq_vehicle_location_events_sequence",
            "vehicle_id",
            "source",
            "sequence",
            unique=True,
            postgresql_where=text("sequence IS NOT NULL"),
        ),
        Index(
            "ix_vehicle_location_events_vehicle_recorded",
            "vehicle_id",
            text("recorded_at DESC"),
        ),
        Index("ix_vehicle_location_events_recorded_at", "recorded_at"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint("accuracy_m IS NULL OR accuracy_m >= 0", name="accuracy_non_negative"),
        CheckConstraint(
            "speed_kph IS NULL OR (speed_kph >= 0 AND speed_kph <= 300)", name="speed_range"
        ),
        CheckConstraint(
            "heading_deg IS NULL OR (heading_deg >= 0 AND heading_deg < 360)", name="heading_range"
        ),
        CheckConstraint("sequence IS NULL OR sequence >= 0", name="sequence_non_negative"),
    )

    vehicle_id: Mapped[uuid.UUID] = fk_uuid(
        "fleet_vehicles.id", index=False
    )  # composite index below
    latitude: Mapped[decimal.Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[decimal.Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    # When the position was measured (device clock, UTC) vs when the server stored it.
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source: Mapped[LocationSource] = mapped_column(enum_column(LocationSource), nullable=False)
    quality: Mapped[LocationQuality] = mapped_column(enum_column(LocationQuality), nullable=False)
    accuracy_m: Mapped[decimal.Decimal | None] = mapped_column(Numeric(9, 2))
    speed_kph: Mapped[decimal.Decimal | None] = mapped_column(Numeric(6, 2))
    heading_deg: Mapped[decimal.Decimal | None] = mapped_column(Numeric(5, 2))
    sequence: Mapped[int | None] = mapped_column(BigInteger)
    collection_task_id: Mapped[uuid.UUID | None] = fk_uuid("collection_tasks.id", nullable=True)
    route_plan_id: Mapped[uuid.UUID | None] = fk_uuid("route_plans.id", nullable=True)
    reported_by_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
