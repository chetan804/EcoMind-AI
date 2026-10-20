"""Community-incident endpoints, mounted at ``/api/v1/community-incidents``."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_any_permission, require_permissions
from app.modules.community_incidents import service
from app.modules.community_incidents.constants import IncidentStatus, IncidentType
from app.modules.community_incidents.schemas import (
    AssignRequest,
    IncidentCreate,
    IncidentOut,
    IncidentSummary,
    SortField,
    StatusRequest,
)

router = APIRouter()

CanReport = Annotated[Principal, Depends(require_permissions("incidents:create"))]
CanView = Annotated[
    Principal, Depends(require_any_permission("incidents:read_own", "incidents:triage"))
]
CanTriage = Annotated[Principal, Depends(require_permissions("incidents:triage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


def _ctx(request: Request) -> RequestContext:
    return RequestContext.from_request(request)


@router.get("", response_model=Page[IncidentOut])
def list_incidents(
    db: DbSession,
    principal: CanView,
    params: Pagination,
    status_filter: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    incident_type: IncidentType | None = None,
    assigned_to_id: uuid.UUID | None = None,
    unassigned: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort_by: SortField = "created_at",
    order: SortOrder = SortOrder.DESC,
) -> Page[IncidentOut]:
    """Triage staff see every incident; everyone else sees only their own reports."""
    return service.list_incidents(
        db,
        principal,
        params,
        status=status_filter,
        incident_type=incident_type,
        assigned_to_id=assigned_to_id,
        unassigned=unassigned,
        q=q,
        sort_by=sort_by,
        order=order,
    )


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate, request: Request, db: DbSession, principal: CanReport
) -> IncidentOut:
    return service.create(db, principal, payload, context=_ctx(request))


@router.get("/summary", response_model=IncidentSummary)
def summary(db: DbSession, _: CanTriage) -> IncidentSummary:
    return service.summary(db)


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: uuid.UUID, db: DbSession, principal: CanView) -> IncidentOut:
    return service.get(db, principal, incident_id)


@router.post("/{incident_id}/assign", response_model=IncidentOut)
def assign_incident(
    incident_id: uuid.UUID,
    payload: AssignRequest,
    request: Request,
    db: DbSession,
    principal: CanTriage,
) -> IncidentOut:
    return service.assign(db, principal, incident_id, payload, context=_ctx(request))


@router.post("/{incident_id}/status", response_model=IncidentOut)
def change_status(
    incident_id: uuid.UUID,
    payload: StatusRequest,
    request: Request,
    db: DbSession,
    principal: CanTriage,
) -> IncidentOut:
    """Move an incident along its lifecycle. Resolving or dismissing requires `notes`."""
    return service.change_status(db, principal, incident_id, payload, context=_ctx(request))
