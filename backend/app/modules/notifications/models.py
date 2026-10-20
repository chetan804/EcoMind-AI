"""In-app notifications. Owned by ``notifications`` (email delivery is an integration)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.notifications.constants import NotificationCategory


class Notification(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_recipient_id_read_at", "recipient_id", "read_at"),)

    recipient_id: Mapped[uuid.UUID] = fk_uuid("users.id", ondelete="CASCADE", index=False)
    category: Mapped[NotificationCategory] = mapped_column(
        enum_column(NotificationCategory), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    # Optional deep link to the entity this notification is about (no FK: polymorphic).
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
