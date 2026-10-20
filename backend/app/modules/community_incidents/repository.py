"""Database access for community incidents. No business rules and no commits here."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.enums import SortOrder
from app.common.pagination import PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.modules.community_incidents.constants import IncidentStatus, IncidentType
from app.modules.community_incidents.models import CommunityIncident

CLOSED = (IncidentStatus.RESOLVED, IncidentStatus.DISMISSED)
_SORT: dict[str, SQLColumnExpression[Any]] = {
    "created_at": CommunityIncident.created_at,
    "updated_at": CommunityIncident.updated_at,
    "status": CommunityIncident.status,
    "incident_type": CommunityIncident.incident_type,
}


def get(
    db: Session, incident_id: uuid.UUID, *, for_update: bool = False
) -> CommunityIncident | None:
    stmt = select(CommunityIncident).where(CommunityIncident.id == incident_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def add(db: Session, **fields: object) -> CommunityIncident:
    incident = CommunityIncident(**fields)
    db.add(incident)
    db.flush()
    return incident


def list_page(
    db: Session,
    params: PageParams,
    *,
    reporter_id: uuid.UUID | None,
    status: IncidentStatus | None,
    incident_type: IncidentType | None,
    assigned_to_id: uuid.UUID | None,
    unassigned: bool,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> tuple[list[CommunityIncident], int]:
    stmt = select(CommunityIncident)
    if reporter_id is not None:
        stmt = stmt.where(CommunityIncident.reporter_id == reporter_id)
    if status is not None:
        stmt = stmt.where(CommunityIncident.status == status)
    if incident_type is not None:
        stmt = stmt.where(CommunityIncident.incident_type == incident_type)
    if assigned_to_id is not None:
        stmt = stmt.where(CommunityIncident.assigned_to_id == assigned_to_id)
    if unassigned:
        stmt = stmt.where(CommunityIncident.assigned_to_id.is_(None))
    pattern = contains_pattern(q) if q else None
    if pattern is not None:
        stmt = stmt.where(
            CommunityIncident.title.ilike(pattern, escape=LIKE_ESCAPE)
            | CommunityIncident.address_text.ilike(pattern, escape=LIKE_ESCAPE)
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _SORT[sort_by]
    direction = column.desc() if order is SortOrder.DESC else column.asc()
    rows = db.execute(
        stmt.order_by(direction, CommunityIncident.id).offset(params.offset).limit(params.limit)
    ).scalars()
    return list(rows), int(total)


def counts(db: Session) -> tuple[dict[IncidentStatus, int], dict[IncidentType, int], int]:
    by_status = {
        s: int(n)
        for s, n in db.execute(
            select(CommunityIncident.status, func.count()).group_by(CommunityIncident.status)
        ).all()
    }
    by_type = {
        t: int(n)
        for t, n in db.execute(
            select(CommunityIncident.incident_type, func.count()).group_by(
                CommunityIncident.incident_type
            )
        ).all()
    }
    unassigned_open = int(
        db.execute(
            select(func.count()).where(
                CommunityIncident.assigned_to_id.is_(None),
                CommunityIncident.status.notin_(CLOSED),
            )
        ).scalar_one()
    )
    return by_status, by_type, unassigned_open
