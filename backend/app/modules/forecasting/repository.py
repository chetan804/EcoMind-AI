"""Database access for reference series and stored forecasts. No commits here."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.forecasting.models import ForecastResult, ReferenceSeries, ReferenceSeriesPoint


def list_reference_series(db: Session) -> list[ReferenceSeries]:
    return list(db.execute(select(ReferenceSeries).order_by(ReferenceSeries.key)).scalars())


def get_reference_series(db: Session, key: str) -> ReferenceSeries | None:
    return db.execute(
        select(ReferenceSeries).where(ReferenceSeries.key == key)
    ).scalar_one_or_none()


def reference_points(db: Session, series_id: uuid.UUID) -> list[ReferenceSeriesPoint]:
    return list(
        db.execute(
            select(ReferenceSeriesPoint)
            .where(ReferenceSeriesPoint.series_id == series_id)
            .order_by(ReferenceSeriesPoint.period_start)
        ).scalars()
    )


def interpolated_count(db: Session, series_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(ReferenceSeriesPoint)
            .where(
                ReferenceSeriesPoint.series_id == series_id,
                ReferenceSeriesPoint.is_interpolated.is_(True),
            )
        ).scalar_one()
    )


def replace_reference_series(
    db: Session,
    *,
    fields: dict[str, object],
    points: Sequence[tuple[dt.date, decimal.Decimal, bool]],
) -> ReferenceSeries:
    """Create the series, or replace an existing one of the same key (points are rewritten)."""
    existing = get_reference_series(db, str(fields["key"]))
    if existing is not None:
        db.delete(existing)
        db.flush()
    series = ReferenceSeries(**fields)
    db.add(series)
    db.flush()
    db.add_all(
        ReferenceSeriesPoint(
            series_id=series.id, period_start=day, value=value, is_interpolated=interpolated
        )
        for day, value, interpolated in points
    )
    db.flush()
    return series


def add_forecast_rows(db: Session, rows: Sequence[ForecastResult]) -> None:
    db.add_all(rows)
    db.flush()


def latest_forecast(db: Session, metric: str) -> list[ForecastResult]:
    newest = (
        select(func.max(ForecastResult.generated_at))
        .where(ForecastResult.metric == metric)
        .scalar_subquery()
    )
    return list(
        db.execute(
            select(ForecastResult)
            .where(ForecastResult.metric == metric, ForecastResult.generated_at == newest)
            .order_by(ForecastResult.period_start)
        ).scalars()
    )
