"""Complaint management with SLA tracking and citizen-visible comments."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class ComplaintCategory(str, enum.Enum):
    missed_collection = "missed_collection"
    bin_damaged = "bin_damaged"
    overflow = "overflow"
    odor = "odor"
    illegal_dumping = "illegal_dumping"
    staff_conduct = "staff_conduct"
    billing = "billing"
    app_issue = "app_issue"
    other = "other"


class ComplaintStatus(str, enum.Enum):
    submitted = "submitted"
    triaged = "triaged"
    assigned = "assigned"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"
    rejected = "rejected"


class ComplaintPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class Complaint(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "complaints"

    waste_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("waste_reports.id", ondelete="SET NULL")
    )
    reporter_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    complainant_contact: Mapped[str | None] = mapped_column(String(320))

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[ComplaintCategory] = mapped_column(
        SAEnum(ComplaintCategory, native_enum=False, length=32),
        default=ComplaintCategory.other,
        nullable=False,
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        SAEnum(ComplaintStatus, native_enum=False, length=24),
        default=ComplaintStatus.submitted,
        nullable=False,
        index=True,
    )
    priority: Mapped[ComplaintPriority] = mapped_column(
        SAEnum(ComplaintPriority, native_enum=False, length=16), default=ComplaintPriority.medium, nullable=False
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    satisfaction_rating: Mapped[int | None] = mapped_column(Integer)  # 1..5 on closure

    __table_args__ = (
        Index("ix_complaints_org_status", "organization_id", "status"),
        Index("ix_complaints_org_created", "organization_id", "created_at"),
    )


class ComplaintComment(UUIDMixin, Base):
    __tablename__ = "complaint_comments"

    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
