"""Create in-app notifications. The caller owns the transaction (no commit here)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.notifications.constants import NotificationCategory
from app.modules.notifications.models import Notification


def notify(
    db: Session,
    *,
    recipient_id: uuid.UUID,
    category: NotificationCategory,
    title: str,
    body: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> Notification:
    notification = Notification(
        recipient_id=recipient_id,
        category=category,
        title=title[:200],
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(notification)
    db.flush()
    return notification
