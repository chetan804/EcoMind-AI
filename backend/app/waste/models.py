"""Waste domain: categories, citizen reports, report lifecycle events."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class ReportStatus(str, enum.Enum):
    submitted = "submitted"
    triaged = "triaged"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"
    closed = "closed"


class ReportSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class ReportSource(str, enum.Enum):
    citizen_app = "citizen_app"
    web = "web"
    field = "field"
    hotline = "hotline"


class WasteCategory(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "waste_categories"

    code: Mapped[str] = mapped_column(String(48), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color_hex: Mapped[str] = mapped_column(String(9), default="#64748b", nullable=False)
    icon: Mapped[str] = mapped_column(String(48), default="trash", nullable=False)
    default_handling_guidance: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("organization_id", "code", name="uq_waste_category_code"),
    )


class WasteReport(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "waste_reports"

    # Ownership: authenticated reporter OR controlled anonymous submission.
    reporter_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Coarse, salted identifier used ONLY for anonymous abuse rate-limiting.
    anon_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    contact: Mapped[str | None] = mapped_column(String(320))

    description: Mapped[str | None] = mapped_column(Text)
    photo_media_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    category_guess: Mapped[str | None] = mapped_column(String(48))
    confirmed_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("waste_categories.id", ondelete="SET NULL")
    )

    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    location_accuracy_m: Mapped[float | None] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(320))
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))

    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, native_enum=False, length=24),
        default=ReportStatus.submitted,
        nullable=False,
        index=True,
    )
    severity: Mapped[ReportSeverity] = mapped_column(
        SAEnum(ReportSeverity, native_enum=False, length=16), default=ReportSeverity.medium, nullable=False
    )
    source: Mapped[ReportSource] = mapped_column(
        SAEnum(ReportSource, native_enum=False, length=16), default=ReportSource.citizen_app, nullable=False
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    ai_inference_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_inferences.id", ondelete="SET NULL", use_alter=True)
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_waste_reports_org_status", "organization_id", "status"),
        Index("ix_waste_reports_org_created", "organization_id", "created_at"),
    )


class WasteReportEvent(UUIDMixin, Base):
    """Append-only lifecycle timeline for a report."""

    __tablename__ = "waste_report_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("waste_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str | None] = mapped_column(String(24))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
