"""Waste reports and uploaded media assets. Owned by the ``waste_reports`` module."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, Numeric, String, Text, func
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
from app.modules.waste_reports.constants import WasteReportStatus


class WasteReport(UUIDPrimaryKeyMixin, TimestampMixin, GeoPointMixin, Base):
    __tablename__ = "waste_reports"
    __table_args__ = (
        CheckConstraint(
            "estimated_weight_kg IS NULL OR estimated_weight_kg >= 0", name="weight_non_negative"
        ),
        *geo_point_constraints(),
    )

    reporter_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    status: Mapped[WasteReportStatus] = mapped_column(
        enum_column(WasteReportStatus),
        nullable=False,
        index=True,
        server_default=WasteReportStatus.SUBMITTED.value,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    address_text: Mapped[str | None] = mapped_column(String(500))
    estimated_weight_kg: Mapped[decimal.Decimal | None] = mapped_column(Numeric(12, 3))
    reported_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class MediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Metadata for a stored file. The bytes live in the configured file-storage backend."""

    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("length(sha256) = 64", name="sha256_hex_length"),
    )

    uploaded_by_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    # Null until the upload is attached to a report (upload -> classify -> submit flow).
    waste_report_id: Mapped[uuid.UUID | None] = fk_uuid(
        "waste_reports.id", nullable=True, ondelete="SET NULL"
    )
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
