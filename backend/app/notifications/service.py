"""Notification service: in-app notifications with channel abstraction.

Email/SMS/push are transport adapters behind ``dispatch``; V1 delivers in-app
records and logs email content (no SMTP configured in development). No
notification is ever fabricated: every row corresponds to a real system event.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, update

from app.core.db import AsyncSession, utcnow
from app.core.logging import get_logger
from app.notifications.models import Notification, NotificationCategory

log = get_logger("notifications")


async def notify_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    category: NotificationCategory | str,
    title: str,
    body: str | None = None,
    data: dict | None = None,
) -> Notification:
    n = Notification(
        organization_id=organization_id,
        recipient_user_id=user_id,
        category=category if isinstance(category, NotificationCategory) else NotificationCategory(category),
        title=title[:200],
        body=(body or "")[:1000] or None,
        data=data or {},
    )
    session.add(n)
    return n


async def notify_role(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    role_codes: list[str],
    category: NotificationCategory | str,
    title: str,
    body: str | None = None,
    data: dict | None = None,
) -> int:
    """Notify every active member of the org holding one of the given roles."""
    from app.orgs.models import OrgMembership

    rows = (
        await session.execute(
            select(OrgMembership.user_id).where(
                OrgMembership.organization_id == organization_id,
                OrgMembership.role_code.in_(role_codes),
                OrgMembership.is_active.is_(True),
            )
        )
    ).scalars().all()
    for uid in rows:
        await notify_user(
            session,
            user_id=uid,
            organization_id=organization_id,
            category=category,
            title=title,
            body=body,
            data=data,
        )
    return len(rows)


async def mark_read(session: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    result = await session.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.recipient_user_id == user_id,
        )
        .values(read_at=utcnow())
    )
    return result.rowcount > 0


async def mark_all_read(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        update(Notification)
        .where(Notification.recipient_user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    return result.rowcount or 0
