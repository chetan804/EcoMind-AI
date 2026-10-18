"""Collection tasks, assignments, status history and collection events.

Owned by the ``collection`` module. Status changes must go through the service so that a
``CollectionTaskStatusHistory`` row is written in the same transaction.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    CreatedAtMixin,
    GeoPointMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    fk_uuid,
    geo_point_constraints,
)
from app.modules.collection.constants import CollectionEventType, CollectionTaskStatus, TaskPriority


class CollectionTask(UUIDPrimaryKeyMixin, TimestampMixin, GeoPointMixin, Base):
    __tablename__ = "collection_tasks"
    __table_args__ = geo_point_constraints()

    waste_report_id: Mapped[uuid.UUID | None] = fk_uuid("waste_reports.id", nullable=True)
    destination_facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    created_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[CollectionTaskStatus] = mapped_column(
        enum_column(CollectionTaskStatus),
        nullable=False,
        index=True,
        server_default=CollectionTaskStatus.PENDING.value,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        enum_column(TaskPriority),
        nullable=False,
        server_default=TaskPriority.NORMAL.value,
    )
    address_text: Mapped[str | None] = mapped_column(String(500))
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class CollectionAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collection_assignments"
    __table_args__ = (
        CheckConstraint(
            "unassigned_at IS NULL OR unassigned_at >= assigned_at",
            name="unassigned_after_assigned",
        ),
        # At most one active (not unassigned) assignment per task.
        Index(
            "uq_collection_assignments_active_task",
            "collection_task_id",
            unique=True,
            postgresql_where=text("unassigned_at IS NULL"),
        ),
    )

    collection_task_id: Mapped[uuid.UUID] = fk_uuid("collection_tasks.id", ondelete="CASCADE")
    assignee_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    vehicle_id: Mapped[uuid.UUID | None] = fk_uuid("fleet_vehicles.id", nullable=True)
    assigned_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    assigned_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    unassigned_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class CollectionTaskStatusHistory(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only log of status transitions."""

    __tablename__ = "collection_task_status_history"

    collection_task_id: Mapped[uuid.UUID] = fk_uuid("collection_tasks.id", ondelete="CASCADE")
    from_status: Mapped[CollectionTaskStatus | None] = mapped_column(
        enum_column(CollectionTaskStatus)
    )
    to_status: Mapped[CollectionTaskStatus] = mapped_column(
        enum_column(CollectionTaskStatus), nullable=False
    )
    changed_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    note: Mapped[str | None] = mapped_column(Text)


class CollectionEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, GeoPointMixin, Base):
    """Something that happened in the field for a task (arrival, pick-up, delivery...)."""

    __tablename__ = "collection_events"
    __table_args__ = (
        CheckConstraint(
            "collected_weight_kg IS NULL OR collected_weight_kg >= 0", name="weight_non_negative"
        ),
        *geo_point_constraints(),
    )

    collection_task_id: Mapped[uuid.UUID] = fk_uuid("collection_tasks.id", ondelete="CASCADE")
    event_type: Mapped[CollectionEventType] = mapped_column(
        enum_column(CollectionEventType), nullable=False
    )
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    recorded_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    collected_weight_kg: Mapped[decimal.Decimal | None] = mapped_column(Numeric(12, 3))
    notes: Mapped[str | None] = mapped_column(Text)
