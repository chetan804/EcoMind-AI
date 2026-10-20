"""Collection task use cases (the operational core of the platform).

Authorisation
    * ``collection:read``    list / view tasks
    * ``collection:manage``  create, assign, cancel, reschedule; may also act for any collector
    * ``collection:execute`` work a task: only when the caller is its ACTIVE assignee

Every status change goes through ``_transition`` so that (a) only edges in ``ALLOWED_TRANSITIONS``
are possible, (b) the task row is locked, and (c) an append-only history row is written in the
same transaction. Completion also closes the linked report, records the reporter's reward
(idempotent) and notifies the reporter; failures roll the whole request back.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import AppError, ForbiddenError, NotFoundError, UnprocessableError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.collection import repository
from app.modules.collection.constants import (
    ALLOWED_TRANSITIONS,
    MANUAL_EVENT_TYPES,
    CollectionEventType,
    CollectionTaskStatus,
    TaskPriority,
)
from app.modules.collection.models import CollectionTask
from app.modules.collection.schemas import (
    AssignmentOut,
    AssignRequest,
    CompleteRequest,
    EventCreate,
    EventOut,
    HistoryOut,
    RescheduleRequest,
    TaskCreate,
    TaskDetail,
    TaskOut,
)
from app.modules.facilities import repository as facilities
from app.modules.facilities.constants import FacilityStatus
from app.modules.fleet import repository as fleet
from app.modules.fleet.constants import VehicleStatus
from app.modules.notifications import service as notifications
from app.modules.notifications.constants import NotificationCategory
from app.modules.rewards import service as rewards
from app.modules.users import repository as users
from app.modules.waste_reports import repository as reports
from app.modules.waste_reports.constants import WasteReportStatus

MANAGE = "collection:manage"
EXECUTE = "collection:execute"
CLOCK_SKEW = dt.timedelta(minutes=5)


class InvalidTransitionError(AppError):
    status_code = 409
    code = "invalid_task_transition"


class ReportNotVerifiedError(AppError):
    status_code = 409
    code = "report_not_verified"


class ReportHasOpenTaskError(AppError):
    status_code = 409
    code = "report_has_open_task"


class VehicleUnavailableError(AppError):
    status_code = 409
    code = "vehicle_unavailable"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ------------------------------------------------------------------------------ presentation
def _task_out(db: Session, tasks: list[CollectionTask]) -> list[TaskOut]:
    ids = [t.id for t in tasks]
    assignments = repository.latest_assignments(db, ids)
    weights = repository.collected_weights(db, ids)
    out = []
    for task in tasks:
        item = TaskOut.model_validate(task, from_attributes=True)
        if task.id in assignments:
            assignment, name, registration = assignments[task.id]
            item.assignment = AssignmentOut(
                id=assignment.id,
                assignee_id=assignment.assignee_id,
                assignee_name=name,
                vehicle_id=assignment.vehicle_id,
                vehicle_registration=registration,
                assigned_at=assignment.assigned_at,
                unassigned_at=assignment.unassigned_at,
            )
        item.collected_weight_kg = weights.get(task.id)
        out.append(item)
    return out


def _detail(db: Session, task: CollectionTask) -> TaskDetail:
    base = _task_out(db, [task])[0]
    return TaskDetail(
        **base.model_dump(),
        history=[HistoryOut.model_validate(h) for h in repository.history(db, task.id)],
        events=[EventOut.model_validate(e) for e in repository.events(db, task.id)],
    )


def _locked(db: Session, task_id: uuid.UUID) -> CollectionTask:
    task = repository.get(db, task_id, for_update=True)
    if task is None:
        raise NotFoundError("Collection task not found")
    return task


def _transition(
    db: Session,
    task: CollectionTask,
    to: CollectionTaskStatus,
    actor: Principal,
    note: str | None,
) -> None:
    if to not in ALLOWED_TRANSITIONS[task.status]:
        db.rollback()
        raise InvalidTransitionError(f"A {task.status.value} task cannot become {to.value}")
    repository.add_history(db, task.id, task.status, to, actor.user_id, note)
    task.status = to


def _ensure_edge(db: Session, task: CollectionTask, to: CollectionTaskStatus) -> None:
    """Reject an impossible move before looking at who asks (a finished task is a 409, not 403)."""
    if to not in ALLOWED_TRANSITIONS[task.status]:
        db.rollback()
        raise InvalidTransitionError(f"A {task.status.value} task cannot become {to.value}")


def _end_assignment(db: Session, task: CollectionTask) -> None:
    current = repository.active_assignment(db, task.id)
    if current is not None:
        current.unassigned_at = _now()
        db.flush()


def _require_actor(db: Session, task: CollectionTask, principal: Principal) -> None:
    """Managers act for anyone; collectors only on a task currently assigned to them."""
    if principal.has(MANAGE):
        return
    current = repository.active_assignment(db, task.id)
    if principal.has(EXECUTE) and current is not None and current.assignee_id == principal.user_id:
        return
    db.rollback()
    raise ForbiddenError("Only the collector assigned to this task can do that")


def _active_facility_id(db: Session, facility_id: uuid.UUID | None, field: str) -> None:
    if facility_id is None:
        return
    facility = facilities.get(db, facility_id)
    if facility is None or facility.status is not FacilityStatus.ACTIVE:
        raise UnprocessableError(f"{field} must refer to an active facility")


def _audit(
    db: Session,
    action: str,
    task: CollectionTask,
    principal: Principal,
    context: RequestContext,
    changes: dict[str, Any],
) -> None:
    audit.record(
        db,
        action=action,
        entity_type="collection_task",
        entity_id=task.id,
        actor_id=principal.user_id,
        context=context,
        changes=changes,
    )


# ------------------------------------------------------------------------------------ queries
def list_tasks(
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
) -> Page[TaskOut]:
    rows, total = repository.list_page(
        db,
        params,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        waste_report_id=waste_report_id,
        due_before=due_before,
        due_after=due_after,
        q=q,
        sort_by=sort_by,
        order=order,
    )
    return Page.build(_task_out(db, rows), total, params)


def get_task(db: Session, task_id: uuid.UUID) -> TaskDetail:
    task = repository.get(db, task_id)
    if task is None:
        raise NotFoundError("Collection task not found")
    return _detail(db, task)


# ------------------------------------------------------------------------------------ commands
def create_task(
    db: Session, principal: Principal, payload: TaskCreate, *, context: RequestContext
) -> TaskDetail:
    fields = payload.model_dump(exclude={"waste_report_id"})
    if payload.waste_report_id is not None:
        report = reports.get(db, payload.waste_report_id, for_update=True)
        if report is None:
            raise UnprocessableError("waste_report_id does not refer to an existing report")
        if report.status is not WasteReportStatus.VERIFIED:
            raise ReportNotVerifiedError(
                "Only verified reports can be scheduled for collection "
                f"(this one is {report.status.value})"
            )
        if repository.open_task_for_report(db, report.id) is not None:
            raise ReportHasOpenTaskError("This report already has an open collection task")
        fields["title"] = payload.title or f"Collect: {report.title}"[:200]
        if payload.latitude is None:
            fields.update(latitude=report.latitude, longitude=report.longitude)
        fields["address_text"] = payload.address_text or report.address_text
    if fields["latitude"] is None and not fields["address_text"]:
        db.rollback()
        raise UnprocessableError("A task needs a location: coordinates or an address")
    _active_facility_id(db, payload.destination_facility_id, "destination_facility_id")
    if payload.due_at is not None and payload.due_at < _now() - CLOCK_SKEW:
        db.rollback()
        raise UnprocessableError("due_at cannot be in the past")
    task = repository.add(
        db, waste_report_id=payload.waste_report_id, created_by_id=principal.user_id, **fields
    )
    repository.add_history(db, task.id, None, CollectionTaskStatus.PENDING, principal.user_id, None)
    _audit(
        db,
        "collection_task.created",
        task,
        principal,
        context,
        {"waste_report_id": str(payload.waste_report_id) if payload.waste_report_id else None},
    )
    db.commit()
    db.refresh(task)
    return _detail(db, task)


def assign(
    db: Session,
    principal: Principal,
    task_id: uuid.UUID,
    payload: AssignRequest,
    *,
    context: RequestContext,
) -> TaskDetail:
    task = _locked(db, task_id)
    assignee = users.get_by_id(db, payload.assignee_id)
    if assignee is None or not assignee.is_active:
        db.rollback()
        raise UnprocessableError("assignee_id must refer to an active user")
    if EXECUTE not in users.permission_codes(db, assignee.id):
        db.rollback()
        raise UnprocessableError("The assignee's role cannot execute collection tasks")
    if payload.vehicle_id is not None:
        vehicle = fleet.get(db, payload.vehicle_id)
        if vehicle is None:
            db.rollback()
            raise UnprocessableError("vehicle_id does not refer to an existing vehicle")
        if vehicle.status in (VehicleStatus.MAINTENANCE, VehicleStatus.RETIRED):
            db.rollback()
            raise VehicleUnavailableError(f"Vehicle is {vehicle.status.value} and cannot be used")
    reassigned = task.status is CollectionTaskStatus.ASSIGNED
    _transition(
        db,
        task,
        CollectionTaskStatus.ASSIGNED,
        principal,
        payload.note or ("reassigned" if reassigned else None),
    )
    _end_assignment(db, task)
    repository.add_assignment(
        db,
        collection_task_id=task.id,
        assignee_id=assignee.id,
        vehicle_id=payload.vehicle_id,
        assigned_by_id=principal.user_id,
    )
    notifications.notify(
        db,
        recipient_id=assignee.id,
        category=NotificationCategory.COLLECTION,
        title="New collection task assigned",
        body=task.title,
        entity_type="collection_task",
        entity_id=task.id,
    )
    _audit(
        db,
        "collection_task.assigned",
        task,
        principal,
        context,
        {
            "assignee_id": str(assignee.id),
            "vehicle_id": str(payload.vehicle_id) if payload.vehicle_id else None,
            "reassigned": reassigned,
        },
    )
    db.commit()
    db.refresh(task)
    return _detail(db, task)


def start(
    db: Session, principal: Principal, task_id: uuid.UUID, *, context: RequestContext
) -> TaskDetail:
    task = _locked(db, task_id)
    _ensure_edge(db, task, CollectionTaskStatus.IN_PROGRESS)
    _require_actor(db, task, principal)
    _transition(db, task, CollectionTaskStatus.IN_PROGRESS, principal, None)
    _audit(db, "collection_task.started", task, principal, context, {})
    db.commit()
    db.refresh(task)
    return _detail(db, task)


def record_event(
    db: Session,
    principal: Principal,
    task_id: uuid.UUID,
    payload: EventCreate,
    *,
    context: RequestContext,
) -> TaskDetail:
    task = _locked(db, task_id)
    if task.status is not CollectionTaskStatus.IN_PROGRESS:
        db.rollback()
        raise InvalidTransitionError("Events can only be recorded while the task is in progress")
    _require_actor(db, task, principal)
    if payload.event_type not in MANUAL_EVENT_TYPES:
        db.rollback()
        raise UnprocessableError(
            "Record the pick-up with POST /collection/tasks/{id}/complete (it carries the weight)"
        )
    if payload.event_type is CollectionEventType.DELIVERED_TO_FACILITY and not payload.facility_id:
        db.rollback()
        raise UnprocessableError("facility_id is required for delivered_to_facility")
    _active_facility_id(db, payload.facility_id, "facility_id")
    occurred = payload.occurred_at or _now()
    if occurred > _now() + CLOCK_SKEW:
        db.rollback()
        raise UnprocessableError("occurred_at cannot be in the future")
    event = repository.add_event(
        db,
        collection_task_id=task.id,
        event_type=payload.event_type,
        occurred_at=occurred,
        recorded_by_id=principal.user_id,
        facility_id=payload.facility_id,
        notes=payload.notes,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    _audit(
        db,
        f"collection_task.event.{payload.event_type.value}",
        task,
        principal,
        context,
        {"event_id": str(event.id)},
    )
    db.commit()
    db.refresh(task)
    return _detail(db, task)


def complete(
    db: Session,
    principal: Principal,
    task_id: uuid.UUID,
    payload: CompleteRequest,
    *,
    points_per_kg: int,
    context: RequestContext,
) -> TaskDetail:
    task = _locked(db, task_id)
    _ensure_edge(db, task, CollectionTaskStatus.COMPLETED)
    _require_actor(db, task, principal)
    destination = payload.destination_facility_id or task.destination_facility_id
    _active_facility_id(db, destination, "destination_facility_id")
    _transition(db, task, CollectionTaskStatus.COMPLETED, principal, payload.notes)
    now = _now()
    repository.add_event(
        db,
        collection_task_id=task.id,
        event_type=CollectionEventType.COLLECTED,
        occurred_at=now,
        recorded_by_id=principal.user_id,
        facility_id=destination,
        collected_weight_kg=payload.collected_weight_kg,
        notes=payload.notes,
        latitude=task.latitude,
        longitude=task.longitude,
    )
    if destination is not None and task.destination_facility_id is None:
        task.destination_facility_id = destination
    _end_assignment(db, task)
    effects: dict[str, Any] = {"collected_weight_kg": str(payload.collected_weight_kg)}
    if task.waste_report_id is not None:
        report = reports.get(db, task.waste_report_id, for_update=True)
        if report is not None:
            if report.status is WasteReportStatus.VERIFIED:
                report.status = WasteReportStatus.CLOSED
            entry = rewards.award_for_collection(
                db,
                user_id=report.reporter_id,
                task_id=task.id,
                weight_kg=decimal.Decimal(payload.collected_weight_kg),
                points_per_kg=points_per_kg,
                created_by_id=principal.user_id,
            )
            if entry is not None:
                effects["reward_points"] = entry.points
            notifications.notify(
                db,
                recipient_id=report.reporter_id,
                category=NotificationCategory.REPORT,
                title="Your reported waste was collected",
                body=f"{report.title}: {payload.collected_weight_kg} kg collected",
                entity_type="waste_report",
                entity_id=report.id,
            )
    _audit(db, "collection_task.completed", task, principal, context, effects)
    db.commit()
    db.refresh(task)
    return _detail(db, task)


def fail(
    db: Session,
    principal: Principal,
    task_id: uuid.UUID,
    reason: str,
    *,
    context: RequestContext,
) -> TaskDetail:
    task = _locked(db, task_id)
    _ensure_edge(db, task, CollectionTaskStatus.FAILED)
    _require_actor(db, task, principal)
    _transition(db, task, CollectionTaskStatus.FAILED, principal, reason)
    _end_assignment(db, task)
    _audit(db, "collection_task.failed", task, principal, context, {"reason": reason})
    db.commit()
    db.refresh(task)
    return _detail(db, task)


def cancel(
    db: Session,
    principal: Principal,
    task_id: uuid.UUID,
    reason: str,
    *,
    context: RequestContext,
) -> TaskDetail:
    task = _locked(db, task_id)
    _transition(db, task, CollectionTaskStatus.CANCELLED, principal, reason)
    _end_assignment(db, task)
    _audit(db, "collection_task.cancelled", task, principal, context, {"reason": reason})
    db.commit()
    db.refresh(task)
    return _detail(db, task)


def reschedule(
    db: Session,
    principal: Principal,
    task_id: uuid.UUID,
    payload: RescheduleRequest,
    *,
    context: RequestContext,
) -> TaskDetail:
    """A failed task returns to ``pending`` with a new due date; an open task keeps its status
    and just gets the new date (recorded as a history row so the change is traceable)."""
    task = _locked(db, task_id)
    if payload.due_at < _now() - CLOCK_SKEW:
        db.rollback()
        raise UnprocessableError("due_at cannot be in the past")
    old = task.due_at
    if task.status is CollectionTaskStatus.FAILED:
        _transition(
            db, task, CollectionTaskStatus.PENDING, principal, payload.note or "rescheduled"
        )
    elif task.status in (CollectionTaskStatus.PENDING, CollectionTaskStatus.ASSIGNED):
        repository.add_history(
            db,
            task.id,
            task.status,
            task.status,
            principal.user_id,
            f"due date changed to {payload.due_at.isoformat()}"
            + (f": {payload.note}" if payload.note else ""),
        )
    else:
        db.rollback()
        raise InvalidTransitionError(f"A {task.status.value} task cannot be rescheduled")
    task.due_at = payload.due_at
    _audit(
        db,
        "collection_task.rescheduled",
        task,
        principal,
        context,
        {"from": old.isoformat() if old else None, "to": payload.due_at.isoformat()},
    )
    db.commit()
    db.refresh(task)
    return _detail(db, task)


def weekly_collected_weight_kg(db: Session) -> list[tuple[dt.date, decimal.Decimal]]:
    """Read interface for other modules (forecasting, analytics): weekly collected kg."""
    return repository.weekly_collected_weight(db)
