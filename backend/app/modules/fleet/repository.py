"""Database access for fleet vehicles. No business rules and no commits here."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.enums import SortOrder
from app.common.pagination import PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.modules.collection.constants import CollectionTaskStatus
from app.modules.collection.models import CollectionAssignment, CollectionTask
from app.modules.fleet.constants import VehicleStatus, VehicleType
from app.modules.fleet.models import FleetVehicle

_SORT_COLUMNS: dict[str, SQLColumnExpression[Any]] = {
    "registration_number": FleetVehicle.registration_number,
    "capacity_kg": FleetVehicle.capacity_kg,
    "status": FleetVehicle.status,
    "created_at": FleetVehicle.created_at,
}
_OPEN = (
    CollectionTaskStatus.PENDING,
    CollectionTaskStatus.ASSIGNED,
    CollectionTaskStatus.IN_PROGRESS,
)


def get(db: Session, vehicle_id: uuid.UUID, *, for_update: bool = False) -> FleetVehicle | None:
    stmt = select(FleetVehicle).where(FleetVehicle.id == vehicle_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def add(db: Session, **fields: object) -> FleetVehicle:
    vehicle = FleetVehicle(**fields)
    db.add(vehicle)
    db.flush()
    return vehicle


def active_task_counts(db: Session, vehicle_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Open tasks (assignment not ended, task not finished) per vehicle."""
    if not vehicle_ids:
        return {}
    stmt = (
        select(CollectionAssignment.vehicle_id, func.count())
        .join(CollectionTask, CollectionTask.id == CollectionAssignment.collection_task_id)
        .where(
            CollectionAssignment.vehicle_id.in_(vehicle_ids),
            CollectionAssignment.unassigned_at.is_(None),
            CollectionTask.status.in_(_OPEN),
        )
        .group_by(CollectionAssignment.vehicle_id)
    )
    return {vid: count for vid, count in db.execute(stmt).all() if vid is not None}


def list_page(
    db: Session,
    params: PageParams,
    *,
    vehicle_type: VehicleType | None,
    status: VehicleStatus | None,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> tuple[list[FleetVehicle], int]:
    stmt = select(FleetVehicle)
    if vehicle_type is not None:
        stmt = stmt.where(FleetVehicle.vehicle_type == vehicle_type)
    if status is not None:
        stmt = stmt.where(FleetVehicle.status == status)
    pattern = contains_pattern(q) if q else None
    if pattern is not None:
        stmt = stmt.where(FleetVehicle.registration_number.ilike(pattern, escape=LIKE_ESCAPE))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _SORT_COLUMNS[sort_by]
    direction = column.desc() if order is SortOrder.DESC else column.asc()
    page = stmt.order_by(direction, FleetVehicle.id).limit(params.limit).offset(params.offset)
    return list(db.execute(page).scalars()), total
