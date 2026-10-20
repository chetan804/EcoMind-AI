"""Stored forecast results and public reference series. Owned by the ``forecasting`` module.

Rows are written by the forecasting service from ``ml/forecasting`` inference output. Each row
records the model name/version that produced it; baseline models are valid producers.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import QuantityUnit
from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.forecasting.constants import ForecastGranularity


class ForecastResult(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "forecast_results"
    __table_args__ = (
        CheckConstraint("period_end > period_start", name="period_ordered"),
        CheckConstraint(
            "lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound",
            name="interval_ordered",
        ),
        Index("ix_forecast_results_metric_period_start", "metric", "period_start"),
    )

    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[QuantityUnit] = mapped_column(enum_column(QuantityUnit), nullable=False)
    granularity: Mapped[ForecastGranularity] = mapped_column(
        enum_column(ForecastGranularity), nullable=False
    )
    facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
    material_category_id: Mapped[uuid.UUID | None] = fk_uuid(
        "material_categories.id", nullable=True
    )
    period_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    predicted_value: Mapped[decimal.Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    lower_bound: Mapped[decimal.Decimal | None] = mapped_column(Numeric(16, 3))
    upper_bound: Mapped[decimal.Decimal | None] = mapped_column(Numeric(16, 3))
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReferenceSeries(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A *public* time series imported from a documented external source.

    It is NOT data produced by this platform: it exists so forecasting and anomaly detection can
    be exercised on real, long histories before the platform has accumulated its own. Provenance
    and licence notes are mandatory and are shown wherever the series is used.
    """

    __tablename__ = "reference_series"

    key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str | None] = mapped_column(String(80))
    unit: Mapped[QuantityUnit] = mapped_column(enum_column(QuantityUnit), nullable=False)
    granularity: Mapped[ForecastGranularity] = mapped_column(
        enum_column(ForecastGranularity), nullable=False
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    licence_note: Mapped[str] = mapped_column(Text, nullable=False)
    processing_note: Mapped[str] = mapped_column(Text, nullable=False)
    first_period: Mapped[dt.date] = mapped_column(Date, nullable=False)
    last_period: Mapped[dt.date] = mapped_column(Date, nullable=False)
    point_count: Mapped[int] = mapped_column(Integer, nullable=False)


class ReferenceSeriesPoint(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reference_series_points"
    __table_args__ = (
        CheckConstraint("value >= 0", name="value_non_negative"),
        UniqueConstraint("series_id", "period_start", name="series_period"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reference_series.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    value: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    # True when the period had too few observed days and the value was interpolated for fitting.
    is_interpolated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
