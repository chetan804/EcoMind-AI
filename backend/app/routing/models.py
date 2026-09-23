"""Routes and ordered stops.

A route separates two responsibilities:
- the *optimisation model* (which stops, in what sequence, under capacity and
  time-window constraints — solved with OR-Tools), and
- the *road routing* (geometry between stops — OSRM when available, otherwise
  a clearly-labelled straight-line estimate with a road-distance factor).
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class RouteStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class StopStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    skipped = "skipped"
    failed = "failed"


class Route(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "routes"

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[RouteStatus] = mapped_column(
        SAEnum(RouteStatus, native_enum=False, length=16), default=RouteStatus.draft, nullable=False
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))
    driver_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    depot_lat: Mapped[float] = mapped_column(Float, nullable=False)
    depot_lng: Mapped[float] = mapped_column(Float, nullable=False)
    total_distance_km: Mapped[float | None] = mapped_column(Float)
    total_duration_min: Mapped[float | None] = mapped_column(Float)
    planned_weight_kg: Mapped[float | None] = mapped_column(Float)
    stops_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Solver provenance: {"solver": "ortools-cvrp", "fallback_geometry": true, ...}
    optimization: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    geometry: Mapped[dict | None] = mapped_column(JSON)  # GeoJSON LineString (or null)
    geometry_is_estimated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_route_code"),
    )


class RouteStop(UUIDMixin, Base):
    __tablename__ = "route_stops"

    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    route_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    collection_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collection_points.id", ondelete="CASCADE"), nullable=False
    )
    planned_arrival_offset_min: Mapped[float | None] = mapped_column(Float)
    est_distance_from_prev_km: Mapped[float | None] = mapped_column(Float)
    est_duration_from_prev_min: Mapped[float | None] = mapped_column(Float)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[StopStatus] = mapped_column(
        SAEnum(StopStatus, native_enum=False, length=16), default=StopStatus.pending, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weight_kg: Mapped[float | None] = mapped_column(Float)
    skip_reason: Mapped[str | None] = mapped_column(String(200))
    contamination_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("route_id", "sequence_no", name="uq_route_stop_seq"),
    )
