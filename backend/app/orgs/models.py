"""Organizations, operational units, zones (service areas), memberships."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class OrgType(str, enum.Enum):
    municipality = "municipality"
    municipal_corporation = "municipal_corporation"
    private_operator = "private_operator"
    residential_community = "residential_community"
    campus = "campus"
    industrial_facility = "industrial_facility"
    commercial_facility = "commercial_facility"
    nonprofit = "nonprofit"
    other = "other"


class OrgStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    org_type: Mapped[OrgType] = mapped_column(default=OrgType.municipality, nullable=False)
    status: Mapped[OrgStatus] = mapped_column(default=OrgStatus.active, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(320))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    # Clearly-labelled demo tenant: synthetic data, visible banner in UI.
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_citizen_signup: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_anonymous_reports: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    branding: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Org-level operational configuration: thresholds, SLA hours, notification prefs.
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class OperationalUnit(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "operational_units"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_unit_code"),)


class Zone(UUIDMixin, TimestampMixin, TenantScoped, Base):
    """Service area: a named GeoJSON polygon with derived centroid/bbox."""

    __tablename__ = "zones"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("operational_units.id", ondelete="SET NULL")
    )
    color_hex: Mapped[str] = mapped_column(String(9), default="#10b981", nullable=False)
    boundary: Mapped[dict] = mapped_column(JSON, nullable=False)  # GeoJSON Polygon
    centroid_lat: Mapped[float] = mapped_column(nullable=False)
    centroid_lng: Mapped[float] = mapped_column(nullable=False)
    bbox_min_lat: Mapped[float] = mapped_column(nullable=False)
    bbox_min_lng: Mapped[float] = mapped_column(nullable=False)
    bbox_max_lat: Mapped[float] = mapped_column(nullable=False)
    bbox_max_lng: Mapped[float] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_zone_code"),
        Index("ix_zones_org", "organization_id"),
    )


class OrgMembership(UUIDMixin, TimestampMixin, Base):
    """User ↔ organization with a role. Users may belong to many organizations."""

    __tablename__ = "org_memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_code: Mapped[str] = mapped_column(String(48), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )


class OrgInvitation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "org_invitations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role_code: Mapped[str] = mapped_column(String(48), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OrgUsageCounters(Base):
    """Materialised org counters for commercial quota checks (plan limits)."""

    __tablename__ = "org_usage_counters"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    citizen_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    device_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
