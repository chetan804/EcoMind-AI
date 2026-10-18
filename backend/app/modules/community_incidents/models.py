"""Community-reported incidents. Owned by the ``community_incidents`` module."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    GeoPointMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    fk_uuid,
    geo_point_constraints,
)
from app.modules.community_incidents.constants import IncidentStatus, IncidentType


class CommunityIncident(UUIDPrimaryKeyMixin, TimestampMixin, GeoPointMixin, Base):
    __tablename__ = "community_incidents"
    __table_args__ = (
        CheckConstraint(
            "(status IN ('resolved', 'dismissed')) = (resolved_at IS NOT NULL)",
            name="resolution_timestamp_consistent",
        ),
        *geo_point_constraints(),
    )

    reporter_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    assigned_to_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    photo_media_asset_id: Mapped[uuid.UUID | None] = fk_uuid("media_assets.id", nullable=True)
    incident_type: Mapped[IncidentType] = mapped_column(
        enum_column(IncidentType), nullable=False, index=True
    )
    status: Mapped[IncidentStatus] = mapped_column(
        enum_column(IncidentStatus),
        nullable=False,
        index=True,
        server_default=IncidentStatus.OPEN.value,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    address_text: Mapped[str | None] = mapped_column(String(500))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
