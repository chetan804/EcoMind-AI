"""Server-side refresh sessions. Owned by the ``auth`` module."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
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


class MfaFactor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user's TOTP authenticator (RFC 6238). At most one per user.

    The shared secret is stored encrypted (``app.core.crypto``), never in clear. ``confirmed_at``
    is null while enrolment is pending: only a confirmed factor is required at sign-in.
    """

    __tablename__ = "mfa_factors"
    __table_args__ = (UniqueConstraint("user_id", name="uq_mfa_factors_user_id"),)

    user_id: Mapped[uuid.UUID] = fk_uuid("users.id", ondelete="CASCADE", index=False)
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Highest time step already accepted: a code can be used once (replay protection).
    last_used_step: Mapped[int | None] = mapped_column(BigInteger)


class MfaRecoveryCode(UUIDPrimaryKeyMixin, Base):
    """One single-use recovery code. Only a keyed hash of the code is stored."""

    __tablename__ = "mfa_recovery_codes"
    __table_args__ = (
        UniqueConstraint("user_id", "code_hash", name="uq_mfa_recovery_codes_user_id_code_hash"),
    )

    user_id: Mapped[uuid.UUID] = fk_uuid("users.id", ondelete="CASCADE")
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
