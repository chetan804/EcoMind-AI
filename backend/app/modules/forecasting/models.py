"""Stored forecast results. Owned by the ``forecasting`` module.

Rows are written by the forecasting service from ``ml/forecasting`` inference output. Each row
records the model name/version that produced it; baseline models are valid producers.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String
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
