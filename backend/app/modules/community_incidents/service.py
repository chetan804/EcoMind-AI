"""Community-incident use cases.

Citizens and collectors report (``incidents:create``); they see their own reports
(``incidents:read_own``) plus any incident assigned to them; managers triage everything
(``incidents:triage``). The reporter is notified of every status change. Lifecycle::

    open ─▶ acknowledged | dismissed
    acknowledged ─▶ in_progress | resolved | dismissed
    in_progress ─▶ resolved | dismissed
    resolved, dismissed: final (notes required)
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import AppError, NotFoundError, UnprocessableError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.community_incidents import repository
from app.modules.community_incidents.constants import IncidentStatus as S
from app.modules.community_incidents.constants import IncidentType
from app.modules.community_incidents.models import CommunityIncident
from app.modules.community_incidents.schemas import (
    AssignRequest,
    Count,
    IncidentCreate,
    IncidentOut,
    IncidentSummary,
    StatusRequest,
)
from app.modules.notifications import service as notifications
from app.modules.notifications.constants import NotificationCategory
from app.modules.users import repository as users
from app.modules.waste_reports import repository as reports

TRIAGE = "incidents:triage"
MEDIA_PATH = "/api/v1/waste-reports/media/{id}/content"

ALLOWED: dict[S, frozenset[S]] = {
    S.OPEN: frozenset({S.ACKNOWLEDGED, S.DISMISSED}),
    S.ACKNOWLEDGED: frozenset({S.IN_PROGRESS, S.RESOLVED, S.DISMISSED}),
    S.IN_PROGRESS: frozenset({S.RESOLVED, S.DISMISSED}),
    S.RESOLVED: frozenset(),
    S.DISMISSED: frozenset(),
}


class InvalidIncidentTransitionError(AppError):
    status_code = 409
    code = "invalid_incident_transition"


def _out(incident: CommunityIncident) -> IncidentOut:
    out = IncidentOut.model_validate(incident, from_attributes=True)
    if incident.photo_media_asset_id is not None:
        out.photo_content_path = MEDIA_PATH.format(id=incident.photo_media_asset_id)
    return out


def _visible(incident: CommunityIncident | None, principal: Principal) -> CommunityIncident:
    """Own reports, incidents assigned to the caller, or any incident for triage staff.

    Anything else is indistinguishable from a missing incident. Being assigned an incident lets
    the assignee read it (so a collector can open the work they were given) but not change it.
    """
    if incident is None or (
        incident.reporter_id != principal.user_id
        and incident.assigned_to_id != principal.user_id
        and not principal.has(TRIAGE)
    ):
        raise NotFoundError("Incident not found")
    return incident


def create(
    db: Session, principal: Principal, payload: IncidentCreate, *, context: RequestContext
) -> IncidentOut:
    if payload.photo_media_asset_id is not None:
        media = reports.get_media(db, payload.photo_media_asset_id)
        if media is None or media.uploaded_by_id != principal.user_id:
            raise UnprocessableError("photo_media_asset_id must be a file you uploaded")
    incident = repository.add(
        db, **payload.model_dump(), reporter_id=principal.user_id, status=S.OPEN
    )
    audit.record(
        db,
        action="community_incident.created",
        entity_type="community_incident",
        entity_id=incident.id,
        actor_id=principal.user_id,
        context=context,
        changes={"incident_type": incident.incident_type.value},
    )
    db.commit()
    db.refresh(incident)
    return _out(incident)


def list_incidents(
    db: Session,
    principal: Principal,
    params: PageParams,
    *,
    status: S | None,
    incident_type: IncidentType | None,
    assigned_to_id: uuid.UUID | None,
    unassigned: bool,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> Page[IncidentOut]:
    triage = principal.has(TRIAGE)
    rows, total = repository.list_page(
        db,
        params,
        visible_to_id=None if triage else principal.user_id,
        status=status,
        incident_type=incident_type,
        assigned_to_id=assigned_to_id if triage else None,
        unassigned=unassigned and triage,
        q=q,
        sort_by=sort_by,
        order=order,
    )
    return Page.build([_out(r) for r in rows], total, params)


def get(db: Session, principal: Principal, incident_id: uuid.UUID) -> IncidentOut:
    return _out(_visible(repository.get(db, incident_id), principal))


def assign(
    db: Session,
    principal: Principal,
    incident_id: uuid.UUID,
    payload: AssignRequest,
    *,
    context: RequestContext,
) -> IncidentOut:
    incident = repository.get(db, incident_id, for_update=True)
    if incident is None:
        raise NotFoundError("Incident not found")
    if incident.status in repository.CLOSED:
        db.rollback()
        raise InvalidIncidentTransitionError(
            f"A {incident.status.value} incident cannot be assigned"
        )
    assignee = users.get_by_id(db, payload.assignee_id)
    if assignee is None or not assignee.is_active:
        db.rollback()
        raise UnprocessableError("assignee_id must refer to an active user")
    codes = users.permission_codes(db, assignee.id)
    if TRIAGE not in codes and "collection:execute" not in codes:
        db.rollback()
        raise UnprocessableError("The assignee must be triage staff or a collector")
    incident.assigned_to_id = assignee.id
    audit.record(
        db,
        action="community_incident.assigned",
        entity_type="community_incident",
        entity_id=incident.id,
        actor_id=principal.user_id,
        context=context,
        changes={"assignee_id": str(assignee.id)},
    )
    notifications.notify(
        db,
        recipient_id=assignee.id,
        category=NotificationCategory.INCIDENT,
        title="An incident was assigned to you",
        body=incident.title,
        entity_type="community_incident",
        entity_id=incident.id,
    )
    db.commit()
    db.refresh(incident)
    return _out(incident)


def change_status(
    db: Session,
    principal: Principal,
    incident_id: uuid.UUID,
    payload: StatusRequest,
    *,
    context: RequestContext,
) -> IncidentOut:
    incident = repository.get(db, incident_id, for_update=True)
    if incident is None:
        raise NotFoundError("Incident not found")
    target = S(payload.status)
    if target not in ALLOWED[incident.status]:
        db.rollback()
        raise InvalidIncidentTransitionError(
            f"A {incident.status.value} incident cannot become {target.value}"
        )
    before = incident.status
    incident.status = target
    if target in repository.CLOSED:
        incident.resolved_at = dt.datetime.now(dt.UTC)
        incident.resolution_notes = payload.notes
    audit.record(
        db,
        action=f"community_incident.{target.value}",
        entity_type="community_incident",
        entity_id=incident.id,
        actor_id=principal.user_id,
        context=context,
        changes={"from": before.value, "to": target.value},
    )
    notifications.notify(
        db,
        recipient_id=incident.reporter_id,
        category=NotificationCategory.INCIDENT,
        title=f"Your incident report is now {target.value.replace('_', ' ')}",
        body=payload.notes or incident.title,
        entity_type="community_incident",
        entity_id=incident.id,
    )
    db.commit()
    db.refresh(incident)
    return _out(incident)


def summary(db: Session) -> IncidentSummary:
    by_status, by_type, unassigned_open = repository.counts(db)
    closed = sum(by_status.get(s, 0) for s in repository.CLOSED)
    total = sum(by_status.values())
    return IncidentSummary(
        total=total,
        open_incidents=total - closed,
        unassigned_open=unassigned_open,
        by_status=[Count(key=s.value, count=by_status.get(s, 0)) for s in S],
        by_type=[Count(key=t.value, count=by_type.get(t, 0)) for t in IncidentType],
    )
