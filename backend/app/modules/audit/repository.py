"""Read access to the audit log. The log is append-only; this module never updates or deletes."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.users.models import User


def list_page(
    db: Session,
    *,
    offset: int,
    limit: int,
    action: str | None,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    occurred_from: dt.datetime | None,
    occurred_to: dt.datetime | None,
) -> tuple[list[tuple[AuditLog, str | None]], int]:
    """Newest first, each row with the actor's email (``None`` for system actions)."""
    stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if occurred_from is not None:
        stmt = stmt.where(AuditLog.occurred_at >= occurred_from)
    if occurred_to is not None:
        stmt = stmt.where(AuditLog.occurred_at < occurred_to)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id).offset(offset).limit(limit)
    )
    return list(rows), int(total)
