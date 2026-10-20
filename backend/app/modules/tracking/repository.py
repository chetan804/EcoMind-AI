"""Database access for vehicle location events. No business rules and no commits here."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.collection.constants import CollectionTaskStatus
from app.modules.collection.models import CollectionAssignment, CollectionTask
from app.modules.fleet.constants import VehicleStatus
from app.modules.fleet.models import FleetVehicle
from app.modules.tracking.constants import LocationSource
from app.modules.tracking.models import VehicleLocationEvent

Event = VehicleLocationEvent
_WORKING = (CollectionTaskStatus.ASSIGNED, CollectionTaskStatus.IN_PROGRESS)
_IS_SIMULATED = Event.source == LocationSource.SIMULATOR


def add_event(db: Session, **fields: object) -> VehicleLocationEvent:
    event = VehicleLocationEvent(**fields)
    db.add(event)
    db.flush()
    return event


def find_duplicate(
    db: Session,
    *,
    vehicle_id: uuid.UUID,
    source: LocationSource,
    recorded_at: dt.datetime,
    sequence: int | None,
) -> VehicleLocationEvent | None:
    same_identity: ColumnElement[bool] = Event.recorded_at == recorded_at
    if sequence is not None:
        same_identity = same_identity | (Event.sequence == sequence)
    stmt = select(Event).where(
        Event.vehicle_id == vehicle_id, Event.source == source, same_identity
    )
    return db.scalars(stmt.limit(1)).first()


def latest_recorded_at(
    db: Session, vehicle_id: uuid.UUID, *, simulated: bool
) -> dt.datetime | None:
    stmt = select(func.max(Event.recorded_at)).where(
        Event.vehicle_id == vehicle_id, _IS_SIMULATED if simulated else ~_IS_SIMULATED
    )
    return db.scalar(stmt)


def count_since(db: Session, vehicle_id: uuid.UUID, since: dt.datetime) -> int:
    stmt = select(func.count()).where(Event.vehicle_id == vehicle_id, Event.received_at >= since)
    return int(db.scalar(stmt) or 0)


def latest_per_vehicle(
    db: Session, vehicle_ids: Sequence[uuid.UUID], *, include_simulated: bool
) -> list[VehicleLocationEvent]:
    """Newest event per (vehicle, real|simulated) using the (vehicle_id, recorded_at DESC) index."""
    if not vehicle_ids:
        return []
    stmt = (
        select(Event)
        .ext(distinct_on(Event.vehicle_id, _IS_SIMULATED))
        .where(Event.vehicle_id.in_(vehicle_ids))
        .order_by(
            Event.vehicle_id, _IS_SIMULATED, Event.recorded_at.desc(), Event.received_at.desc()
        )
    )
    if not include_simulated:
        stmt = stmt.where(~_IS_SIMULATED)
    return list(db.scalars(stmt))


def list_events(
    db: Session,
    vehicle_id: uuid.UUID,
    params: PageParams,
    *,
    since: dt.datetime | None,
    until: dt.datetime | None,
    source: LocationSource | None,
    include_simulated: bool,
) -> tuple[list[VehicleLocationEvent], int]:
    conditions: list[ColumnElement[bool]] = [Event.vehicle_id == vehicle_id]
    if since is not None:
        conditions.append(Event.recorded_at >= since)
    if until is not None:
        conditions.append(Event.recorded_at <= until)
    if source is not None:
        conditions.append(Event.source == source)
    elif not include_simulated:
        conditions.append(~_IS_SIMULATED)
    total = int(db.scalar(select(func.count()).select_from(Event).where(*conditions)) or 0)
    rows = db.scalars(
        select(Event)
        .where(*conditions)
        .order_by(Event.recorded_at.desc(), Event.id)
        .offset(params.offset)
        .limit(params.limit)
    )
    return list(rows), total


def path(
    db: Session,
    vehicle_id: uuid.UUID,
    *,
    simulated: bool,
    limit: int,
    task_id: uuid.UUID | None = None,
    route_plan_id: uuid.UUID | None = None,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
) -> list[VehicleLocationEvent]:
    """Oldest-first positions, newest ``limit`` of them when more exist."""
    conditions: list[ColumnElement[bool]] = [
        Event.vehicle_id == vehicle_id,
        _IS_SIMULATED if simulated else ~_IS_SIMULATED,
    ]
    if task_id is not None:
        conditions.append(Event.collection_task_id == task_id)
    if route_plan_id is not None:
        conditions.append(Event.route_plan_id == route_plan_id)
    if since is not None:
        conditions.append(Event.recorded_at >= since)
    if until is not None:
        conditions.append(Event.recorded_at < until)
    newest_first = db.scalars(
        select(Event).where(*conditions).order_by(Event.recorded_at.desc()).limit(limit + 1)
    )
    return list(reversed(list(newest_first)))


def delete_simulated(db: Session, vehicle_id: uuid.UUID) -> int:
    result = db.execute(
        delete(Event).where(
            Event.vehicle_id == vehicle_id, Event.source == LocationSource.SIMULATOR
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def purge_before(db: Session, cutoff: dt.datetime) -> int:
    result = db.execute(delete(Event).where(Event.recorded_at < cutoff))
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def trackable_vehicles(
    db: Session, vehicle_ids: Sequence[uuid.UUID] | None = None
) -> list[FleetVehicle]:
    stmt = select(FleetVehicle).where(FleetVehicle.status != VehicleStatus.RETIRED)
    if vehicle_ids is not None:
        stmt = stmt.where(FleetVehicle.id.in_(vehicle_ids))
    return list(db.scalars(stmt.order_by(FleetVehicle.registration_number)))


def assigned_vehicle_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Vehicles the user is currently assigned to through open (assigned / in progress) tasks."""
    stmt = (
        select(CollectionAssignment.vehicle_id)
        .join(CollectionTask, CollectionTask.id == CollectionAssignment.collection_task_id)
        .where(
            CollectionAssignment.assignee_id == user_id,
            CollectionAssignment.unassigned_at.is_(None),
            CollectionAssignment.vehicle_id.is_not(None),
            CollectionTask.status.in_(_WORKING),
        )
        .distinct()
    )
    return [v for v in db.scalars(stmt) if v is not None]


def working_tasks_on_vehicle(
    db: Session, user_id: uuid.UUID, vehicle_id: uuid.UUID
) -> list[CollectionTask]:
    stmt = (
        select(CollectionTask)
        .join(CollectionAssignment, CollectionAssignment.collection_task_id == CollectionTask.id)
        .where(
            CollectionAssignment.assignee_id == user_id,
            CollectionAssignment.vehicle_id == vehicle_id,
            CollectionAssignment.unassigned_at.is_(None),
            CollectionTask.status.in_(_WORKING),
        )
    )
    return list(db.scalars(stmt))


def task_vehicle_id(db: Session, task_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(
        select(CollectionAssignment.vehicle_id).where(
            CollectionAssignment.collection_task_id == task_id,
            CollectionAssignment.unassigned_at.is_(None),
        )
    )


def task_statuses(
    db: Session, task_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, CollectionTaskStatus]:
    if not task_ids:
        return {}
    rows = db.execute(
        select(CollectionTask.id, CollectionTask.status).where(CollectionTask.id.in_(task_ids))
    )
    return {task_id: status for task_id, status in rows}
