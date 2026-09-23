"""Notification endpoints (in-app)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.auth.deps import AuthCtx, DbSession
from app.notifications.models import Notification
from app.notifications.service import mark_all_read, mark_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    category: str
    title: str
    body: str | None
    data: dict
    read_at: datetime | None
    created_at: datetime


@router.get("")
async def list_notifications(ctx: AuthCtx, session: DbSession, unread_only: bool = False, page: int = 1, page_size: int = 20):
    q = select(Notification).where(Notification.recipient_user_id == ctx.user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    unread = (
        await session.execute(
            select(func.count()).select_from(Notification).where(
                Notification.recipient_user_id == ctx.user.id,
                Notification.read_at.is_(None),
            )
        )
    ).scalar_one()
    items = (
        await session.execute(
            q.order_by(Notification.created_at.desc()).limit(min(page_size, 100)).offset((page - 1) * page_size)
        )
    ).scalars().all()
    return {
        "items": [NotificationOut.model_validate(n).model_dump() for n in items],
        "unread": unread,
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


@router.post("/{notification_id}/read")
async def read_endpoint(notification_id: uuid.UUID, ctx: AuthCtx, session: DbSession):
    ok = await mark_read(session, ctx.user.id, notification_id)
    await session.commit()
    return {"ok": ok}


@router.post("/read-all")
async def read_all_endpoint(ctx: AuthCtx, session: DbSession):
    n = await mark_all_read(session, ctx.user.id)
    await session.commit()
    return {"marked": n}
