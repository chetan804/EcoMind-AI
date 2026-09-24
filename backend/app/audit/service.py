"""Audit log service — append-only record of meaningful actions."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.audit.models import AuditEvent
from app.core.db import AsyncSession, utcnow
from app.core.logging import get_logger, request_id_var

log = get_logger("audit")

REDACT_KEYS = {"password", "password_hash", "token", "api_key", "secret", "authorization"}


def _redact(data: dict | None) -> dict | None:
    if not data:
        return data
    return {k: ("[redacted]" if any(r in k.lower() for r in REDACT_KEYS) else v) for k, v in data.items()}


async def record(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_label: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        before=_redact(before),
        after=_redact(after),
        request_id=request_id_var.get(),
        ip=ip,
        user_agent=(user_agent or "")[:255] or None,
        created_at=utcnow(),
    )
    session.add(event)
    return event


async def list_events(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    action_prefix: str | None = None,
    actor_user_id: uuid.UUID | None = None,
):
    q = select(AuditEvent).where(AuditEvent.organization_id == organization_id)
    if action_prefix:
        q = q.where(AuditEvent.action.like(f"{action_prefix}%"))
    if actor_user_id:
        q = q.where(AuditEvent.actor_user_id == actor_user_id)
    total = (
        await session.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    items = (
        await session.execute(q.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return items, total
