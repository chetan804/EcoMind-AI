from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.notifications.constants import NotificationCategory


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: NotificationCategory
    title: str
    body: str | None
    entity_type: str | None
    entity_id: uuid.UUID | None
    read_at: dt.datetime | None
    created_at: dt.datetime


class UnreadCount(BaseModel):
    unread: int


class MarkedRead(BaseModel):
    marked: int
