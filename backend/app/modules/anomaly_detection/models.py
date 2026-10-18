"""Operational anomaly alerts. Owned by the ``anomaly_detection`` module."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import QuantityUnit
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.anomaly_detection.constants import AlertStatus, AnomalySeverity


class AnomalyAlert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "anomaly_alerts"
    __table_args__ = (
        CheckConstraint("window_end > window_start", name="window_ordered"),
        CheckConstraint("length(explanation) > 0", name="explanation_required"),
    )

    metric: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    unit: Mapped[QuantityUnit] = mapped_column(enum_column(QuantityUnit), nullable=False)
    severity: Mapped[AnomalySeverity] = mapped_column(enum_column(AnomalySeverity), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        enum_column(AlertStatus),
        nullable=False,
        index=True,
        server_default=AlertStatus.OPEN.value,
    )
    facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    material_category_id: Mapped[uuid.UUID | None] = fk_uuid(
        "material_categories.id", nullable=True
    )
    window_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_value: Mapped[decimal.Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    expected_value: Mapped[decimal.Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    threshold_value: Mapped[decimal.Decimal | None] = mapped_column(Numeric(16, 3))
    detector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(50), nullable=False)
    # Human-readable reason the alert fired (required: alerts must be explainable).
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    acknowledged_by_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
