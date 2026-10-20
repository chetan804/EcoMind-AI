"""Notification endpoints, mounted at ``/api/v1/notifications``. Always the caller's own."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession
from app.common.pagination import Page, PageParams, page_params
from app.core.exceptions import NotFoundError
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.notifications import repository
from app.modules.notifications.constants import NotificationCategory
from app.modules.notifications.schemas import MarkedRead, NotificationOut, UnreadCount

router = APIRouter()

Own = Annotated[Principal, Depends(require_permissions("notifications:read_own"))]
Pagination = Annotated[PageParams, Depends(page_params)]


@router.get("", response_model=Page[NotificationOut])
def list_notifications(
    db: DbSession,
    principal: Own,
    params: Pagination,
    unread_only: bool = False,
    category: NotificationCategory | None = None,
) -> Page[NotificationOut]:
    rows, total = repository.list_page(
        db, principal.user_id, params, unread_only=unread_only, category=category
    )
    return Page.build(
        [NotificationOut.model_validate(r, from_attributes=True) for r in rows], total, params
    )


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(db: DbSession, principal: Own) -> UnreadCount:
    return UnreadCount(unread=repository.unread_count(db, principal.user_id))


@router.post("/read-all", response_model=MarkedRead)
def read_all(db: DbSession, principal: Own) -> MarkedRead:
    marked = repository.mark_all_read(db, principal.user_id, dt.datetime.now(dt.UTC))
    db.commit()
    return MarkedRead(marked=marked)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: uuid.UUID, db: DbSession, principal: Own) -> NotificationOut:
    """Idempotent. Another user's notification is indistinguishable from a missing one (404)."""
    row = repository.get_own(db, principal.user_id, notification_id)
    if row is None:
        raise NotFoundError("Notification not found")
    if row.read_at is None:
        row.read_at = dt.datetime.now(dt.UTC)
        db.commit()
        db.refresh(row)
    return NotificationOut.model_validate(row, from_attributes=True)
