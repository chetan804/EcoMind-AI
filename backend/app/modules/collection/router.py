"""Collection endpoints, mounted at ``/api/v1/collection``."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import AppSettings, DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_any_permission, require_permissions
from app.modules.collection import service
from app.modules.collection.constants import CollectionTaskStatus, TaskPriority
from app.modules.collection.schemas import (
    AssignRequest,
    CompleteRequest,
    EventCreate,
    ReasonRequest,
    RescheduleRequest,
    SortField,
    TaskCreate,
    TaskDetail,
    TaskOut,
)

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("collection:read"))]
CanManage = Annotated[Principal, Depends(require_permissions("collection:manage"))]
# Collectors may act on their own tasks; the service enforces "own" for non-managers.
CanWork = Annotated[
    Principal, Depends(require_any_permission("collection:execute", "collection:manage"))
]
Pagination = Annotated[PageParams, Depends(page_params)]


def _ctx(request: Request) -> RequestContext:
    return RequestContext.from_request(request)


@router.get("/tasks", response_model=Page[TaskOut])
def list_tasks(
    db: DbSession,
    principal: CanRead,
    params: Pagination,
    status_filter: Annotated[CollectionTaskStatus | None, Query(alias="status")] = None,
    priority: TaskPriority | None = None,
    assignee_id: uuid.UUID | None = None,
    mine: Annotated[bool, Query(description="Only tasks assigned to the caller")] = False,
    waste_report_id: uuid.UUID | None = None,
    due_before: dt.datetime | None = None,
    due_after: dt.datetime | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort_by: SortField = "created_at",
    order: SortOrder = SortOrder.DESC,
) -> Page[TaskOut]:
    return service.list_tasks(
        db,
        params,
        status=status_filter,
        priority=priority,
        assignee_id=principal.user_id if mine else assignee_id,
        waste_report_id=waste_report_id,
        due_before=due_before,
        due_after=due_after,
        q=q,
        sort_by=sort_by,
        order=order,
    )


@router.post("/tasks", response_model=TaskDetail, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate, request: Request, db: DbSession, principal: CanManage
) -> TaskDetail:
    return service.create_task(db, principal, payload, context=_ctx(request))


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: uuid.UUID, db: DbSession, _: CanRead) -> TaskDetail:
    return service.get_task(db, task_id)


@router.post("/tasks/{task_id}/assign", response_model=TaskDetail)
def assign_task(
    task_id: uuid.UUID,
    payload: AssignRequest,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> TaskDetail:
    return service.assign(db, principal, task_id, payload, context=_ctx(request))


@router.post("/tasks/{task_id}/start", response_model=TaskDetail)
def start_task(
    task_id: uuid.UUID, request: Request, db: DbSession, principal: CanWork
) -> TaskDetail:
    return service.start(db, principal, task_id, context=_ctx(request))


@router.post("/tasks/{task_id}/events", response_model=TaskDetail, status_code=201)
def record_event(
    task_id: uuid.UUID,
    payload: EventCreate,
    request: Request,
    db: DbSession,
    principal: CanWork,
) -> TaskDetail:
    return service.record_event(db, principal, task_id, payload, context=_ctx(request))


@router.post("/tasks/{task_id}/complete", response_model=TaskDetail)
def complete_task(
    task_id: uuid.UUID,
    payload: CompleteRequest,
    request: Request,
    db: DbSession,
    principal: CanWork,
    settings: AppSettings,
) -> TaskDetail:
    return service.complete(
        db,
        principal,
        task_id,
        payload,
        points_per_kg=settings.reward_points_per_kg,
        context=_ctx(request),
    )


@router.post("/tasks/{task_id}/fail", response_model=TaskDetail)
def fail_task(
    task_id: uuid.UUID,
    payload: ReasonRequest,
    request: Request,
    db: DbSession,
    principal: CanWork,
) -> TaskDetail:
    return service.fail(db, principal, task_id, payload.reason, context=_ctx(request))


@router.post("/tasks/{task_id}/cancel", response_model=TaskDetail)
def cancel_task(
    task_id: uuid.UUID,
    payload: ReasonRequest,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> TaskDetail:
    return service.cancel(db, principal, task_id, payload.reason, context=_ctx(request))


@router.post("/tasks/{task_id}/reschedule", response_model=TaskDetail)
def reschedule_task(
    task_id: uuid.UUID,
    payload: RescheduleRequest,
    request: Request,
    db: DbSession,
    principal: CanManage,
) -> TaskDetail:
    return service.reschedule(db, principal, task_id, payload, context=_ctx(request))
