"""Route plans and route stops. Owned by the ``route_planning`` module."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.route_planning.constants import RoutePlanStatus


class RoutePlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "route_plans"
    __table_args__ = (
        CheckConstraint(
            "total_distance_km IS NULL OR total_distance_km >= 0", name="distance_non_negative"
        ),
        CheckConstraint(
            "estimated_duration_min IS NULL OR estimated_duration_min >= 0",
            name="duration_non_negative",
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    planned_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[RoutePlanStatus] = mapped_column(
        enum_column(RoutePlanStatus),
        nullable=False,
        index=True,
        server_default=RoutePlanStatus.DRAFT.value,
    )
    vehicle_id: Mapped[uuid.UUID | None] = fk_uuid("fleet_vehicles.id", nullable=True)
    driver_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    start_facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    end_facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    created_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    total_distance_km: Mapped[decimal.Decimal | None] = mapped_column(Numeric(10, 3))
    estimated_duration_min: Mapped[int | None] = mapped_column(Integer)
    # Which optimizer produced the stop order (name + version); null for manually ordered plans.
    optimizer: Mapped[str | None] = mapped_column(String(100))


class RouteStop(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "route_stops"
    __table_args__ = (
        UniqueConstraint("route_plan_id", "sequence", name="uq_route_stops_route_plan_id_sequence"),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
        CheckConstraint(
            "num_nonnulls(collection_task_id, facility_id) = 1", name="exactly_one_target"
        ),
    )

    route_plan_id: Mapped[uuid.UUID] = fk_uuid("route_plans.id", ondelete="CASCADE")
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    collection_task_id: Mapped[uuid.UUID | None] = fk_uuid("collection_tasks.id", nullable=True)
    facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    planned_arrival_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    actual_arrival_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
