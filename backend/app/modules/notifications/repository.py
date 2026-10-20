"""Database access for notifications. Every query is scoped to one recipient."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.notifications.constants import NotificationCategory
from app.modules.notifications.models import Notification


def list_page(
    db: Session,
    recipient_id: uuid.UUID,
    params: PageParams,
    *,
    unread_only: bool,
    category: NotificationCategory | None,
) -> tuple[list[Notification], int]:
    stmt = select(Notification).where(Notification.recipient_id == recipient_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    if category is not None:
        stmt = stmt.where(Notification.category == category)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(Notification.created_at.desc(), Notification.id)
        .offset(params.offset)
        .limit(params.limit)
    ).scalars()
    return list(rows), int(total)


def unread_count(db: Session, recipient_id: uuid.UUID) -> int:
    stmt = select(func.count()).where(
        Notification.recipient_id == recipient_id, Notification.read_at.is_(None)
    )
    return int(db.execute(stmt).scalar_one())


def get_own(
    db: Session, recipient_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification | None:
    return db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.recipient_id == recipient_id
        )
    ).scalar_one_or_none()


def mark_all_read(db: Session, recipient_id: uuid.UUID, now: dt.datetime) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.recipient_id == recipient_id, Notification.read_at.is_(None))
        .values(read_at=now)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
