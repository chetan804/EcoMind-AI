"""Collection operations: points, recurring schedules, per-day events.

The system works with ordinary (non-smart) operations: fill levels are
optional estimates, and smart-bin devices merely enrich a collection point.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class PointKind(str, enum.Enum):
    curbside = "curbside"
    bin_station = "bin_station"
    transfer_station = "transfer_station"
    commercial_dropoff = "commercial_dropoff"
    household = "household"


class ScheduleFrequency(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"


class EventStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    missed = "missed"
    skipped = "skipped"
    partial = "partial"


class CollectionPoint(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "collection_points"

    code: Mapped[str] = mapped_column(String(48), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[PointKind] = mapped_column(
        SAEnum(PointKind, native_enum=False, length=32), default=PointKind.bin_station, nullable=False
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String(320))
    households_served: Mapped[int | None] = mapped_column(Integer)
    capacity_volume_m3: Mapped[float | None] = mapped_column(Float)
    est_fill_pct: Mapped[int | None] = mapped_column(Float)  # manual estimate when no device
    pickup_notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_collection_point_code"),
        Index("ix_collection_points_org", "organization_id"),
    )


class CollectionSchedule(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "collection_schedules"

    collection_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collection_points.id", ondelete="CASCADE"), nullable=False, index=True
    )
    waste_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("waste_categories.id", ondelete="SET NULL")
    )
    frequency: Mapped[ScheduleFrequency] = mapped_column(
        SAEnum(ScheduleFrequency, native_enum=False, length=16), default=ScheduleFrequency.weekly, nullable=False
    )
    weekday: Mapped[int | None] = mapped_column(Integer)  # 0=Mon .. 6=Sun for weekly/biweekly
    weeks_interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    window_start: Mapped[time | None] = mapped_column(DateTime(timezone=False))
    window_end: Mapped[time | None] = mapped_column(DateTime(timezone=False))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CollectionEvent(UUIDMixin, TimestampMixin, TenantScoped, Base):
    """One planned/actual pickup on a specific date for a point."""

    __tablename__ = "collection_events"

    collection_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collection_points.id", ondelete="CASCADE"), nullable=False
    )
    waste_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("waste_categories.id", ondelete="SET NULL")
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus, native_enum=False, length=16), default=EventStatus.scheduled, nullable=False
    )
    route_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("routes.id", ondelete="SET NULL", use_alter=True))
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    collector_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 3))
    volume_m3: Mapped[float | None] = mapped_column(Numeric(12, 3))
    contamination_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(String(48))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "collection_point_id", "scheduled_date",
            name="uq_collection_event_point_date",
        ),
        Index("ix_collection_events_org_date", "organization_id", "scheduled_date"),
        Index("ix_collection_events_org_status", "organization_id", "status"),
    )
