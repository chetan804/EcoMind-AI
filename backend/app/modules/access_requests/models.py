"""Requests for an operational role. Owned by the ``access_requests`` module."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.access_requests.constants import RequestableRole, RequestStatus


class RoleRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "role_requests"
    __table_args__ = (
        CheckConstraint(
            "(status IN ('approved', 'rejected')) = (decided_at IS NOT NULL)",
            name="decision_timestamp_consistent",
        ),
        CheckConstraint(
            "(status IN ('approved', 'rejected')) = (decided_by_id IS NOT NULL)",
            name="decider_consistent",
        ),
        # A person can have only one open request at a time.
        Index(
            "uq_role_requests_one_pending_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    decided_by_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    requested_role: Mapped[RequestableRole] = mapped_column(
        enum_column(RequestableRole), nullable=False, index=True
    )
    status: Mapped[RequestStatus] = mapped_column(
        enum_column(RequestStatus),
        nullable=False,
        index=True,
        server_default=RequestStatus.PENDING.value,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    organisation: Mapped[str | None] = mapped_column(String(200))
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
