"""Database access for collection tasks. No business rules and no commits here."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.enums import SortOrder
from app.common.pagination import PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.modules.collection.constants import (
    CollectionEventType,
    CollectionTaskStatus,
    TaskPriority,
)
from app.modules.collection.models import (
    CollectionAssignment,
    CollectionEvent,
    CollectionTask,
    CollectionTaskStatusHistory,
)
from app.modules.fleet.models import FleetVehicle
from app.modules.users.models import User

_PRIORITY_RANK = case(
    (CollectionTask.priority == TaskPriority.URGENT, 4),
    (CollectionTask.priority == TaskPriority.HIGH, 3),
    (CollectionTask.priority == TaskPriority.NORMAL, 2),
    else_=1,
)
_SORT_COLUMNS: dict[str, SQLColumnExpression[Any]] = {
    "created_at": CollectionTask.created_at,
    "due_at": CollectionTask.due_at,
    "priority": _PRIORITY_RANK,
    "status": CollectionTask.status,
}


def get(db: Session, task_id: uuid.UUID, *, for_update: bool = False) -> CollectionTask | None:
    stmt = select(CollectionTask).where(CollectionTask.id == task_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def add(db: Session, **fields: object) -> CollectionTask:
    task = CollectionTask(**fields)
    db.add(task)
    db.flush()
    return task


def add_history(
    db: Session,
    task_id: uuid.UUID,
    from_status: CollectionTaskStatus | None,
    to_status: CollectionTaskStatus,
    changed_by_id: uuid.UUID,
    note: str | None,
) -> None:
    db.add(
        CollectionTaskStatusHistory(
            collection_task_id=task_id,
            from_status=from_status,
            to_status=to_status,
            changed_by_id=changed_by_id,
            note=note,
        )
    )
    db.flush()


def add_event(db: Session, **fields: object) -> CollectionEvent:
    event = CollectionEvent(**fields)
    db.add(event)
    db.flush()
    return event


def open_task_for_report(db: Session, report_id: uuid.UUID) -> CollectionTask | None:
    return db.scalar(
        select(CollectionTask).where(
            CollectionTask.waste_report_id == report_id,
            CollectionTask.status.in_(
                (
                    CollectionTaskStatus.PENDING,
                    CollectionTaskStatus.ASSIGNED,
                    CollectionTaskStatus.IN_PROGRESS,
                )
            ),
        )
    )


def active_assignment(db: Session, task_id: uuid.UUID) -> CollectionAssignment | None:
    return db.scalar(
        select(CollectionAssignment).where(
            CollectionAssignment.collection_task_id == task_id,
            CollectionAssignment.unassigned_at.is_(None),
        )
    )


def add_assignment(db: Session, **fields: object) -> CollectionAssignment:
    assignment = CollectionAssignment(**fields)
    db.add(assignment)
    db.flush()
    return assignment


def latest_assignments(
    db: Session, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[CollectionAssignment, str, str | None]]:
    """Most recent assignment per task with the assignee's name and vehicle registration."""
    if not task_ids:
        return {}
    stmt = (
        select(CollectionAssignment, User.full_name, FleetVehicle.registration_number)
        .join(User, User.id == CollectionAssignment.assignee_id)
        .outerjoin(FleetVehicle, FleetVehicle.id == CollectionAssignment.vehicle_id)
        .where(CollectionAssignment.collection_task_id.in_(task_ids))
        .order_by(CollectionAssignment.assigned_at.asc(), CollectionAssignment.id)
    )
    out: dict[uuid.UUID, tuple[CollectionAssignment, str, str | None]] = {}
    for assignment, name, registration in db.execute(stmt).all():
        out[assignment.collection_task_id] = (assignment, name, registration)  # last one wins
    return out


def collected_weights(db: Session, task_ids: list[uuid.UUID]) -> dict[uuid.UUID, decimal.Decimal]:
    if not task_ids:
        return {}
    stmt = (
        select(CollectionEvent.collection_task_id, func.sum(CollectionEvent.collected_weight_kg))
        .where(
            CollectionEvent.collection_task_id.in_(task_ids),
            CollectionEvent.event_type == CollectionEventType.COLLECTED,
        )
        .group_by(CollectionEvent.collection_task_id)
    )
    return {tid: total for tid, total in db.execute(stmt).all() if total is not None}


def history(db: Session, task_id: uuid.UUID) -> list[CollectionTaskStatusHistory]:
    return list(
        db.scalars(
            select(CollectionTaskStatusHistory)
            .where(CollectionTaskStatusHistory.collection_task_id == task_id)
            .order_by(CollectionTaskStatusHistory.created_at, CollectionTaskStatusHistory.id)
        )
    )


def events(db: Session, task_id: uuid.UUID) -> list[CollectionEvent]:
    return list(
        db.scalars(
            select(CollectionEvent)
            .where(CollectionEvent.collection_task_id == task_id)
            .order_by(CollectionEvent.occurred_at, CollectionEvent.id)
        )
    )


def list_page(
    db: Session,
    params: PageParams,
    *,
    status: CollectionTaskStatus | None,
    priority: TaskPriority | None,
    assignee_id: uuid.UUID | None,
    waste_report_id: uuid.UUID | None,
    due_before: dt.datetime | None,
    due_after: dt.datetime | None,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> tuple[list[CollectionTask], int]:
    stmt = select(CollectionTask)
    if status is not None:
        stmt = stmt.where(CollectionTask.status == status)
    if priority is not None:
        stmt = stmt.where(CollectionTask.priority == priority)
    if waste_report_id is not None:
        stmt = stmt.where(CollectionTask.waste_report_id == waste_report_id)
    if assignee_id is not None:
        stmt = stmt.where(
            CollectionTask.id.in_(
                select(CollectionAssignment.collection_task_id).where(
                    CollectionAssignment.assignee_id == assignee_id,
                    CollectionAssignment.unassigned_at.is_(None),
                )
            )
        )
    if due_before is not None:
        stmt = stmt.where(CollectionTask.due_at <= due_before)
    if due_after is not None:
        stmt = stmt.where(CollectionTask.due_at >= due_after)
    pattern = contains_pattern(q) if q else None
    if pattern is not None:
        stmt = stmt.where(
            or_(
                CollectionTask.title.ilike(pattern, escape=LIKE_ESCAPE),
                CollectionTask.address_text.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _SORT_COLUMNS[sort_by]
    direction = column.desc() if order is SortOrder.DESC else column.asc()
    page = (
        stmt.order_by(direction.nulls_last(), CollectionTask.id)
        .limit(params.limit)
        .offset(params.offset)
    )
    return list(db.execute(page).scalars()), total
