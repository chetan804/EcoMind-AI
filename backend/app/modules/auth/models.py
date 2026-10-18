"""Server-side refresh sessions. Owned by the ``auth`` module."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, fk_uuid


class AuthSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One issued refresh token. Rotation creates a new row in the same ``family_id``;
    presenting an already-rotated token revokes the whole family (reuse detection)."""

    __tablename__ = "auth_sessions"
    __table_args__ = (CheckConstraint("expires_at > created_at", name="expiry_after_creation"),)

    user_id: Mapped[uuid.UUID] = fk_uuid("users.id", ondelete="CASCADE")
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True, server_default=text("gen_random_uuid()")
    )
    # SHA-256 hex digest of the opaque refresh token. The raw token is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))
