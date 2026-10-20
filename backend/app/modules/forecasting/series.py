"""Loading of the weekly series the forecasting and anomaly modules work on.

Two kinds, never mixed:

* ``platform:collected_weight_kg``: weekly totals of weight recorded by completed collection
  tasks in THIS system. Weeks with no collection are true zeros (the system is the record of
  truth); the series runs from the first week with data to the last *complete* week.
* ``reference:<key>``: a public dataset imported with provenance (``ReferenceSeries``).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.common.enums import QuantityUnit
from app.core.exceptions import NotFoundError
from app.modules.collection import service as collection
from app.modules.forecasting import repository
from app.modules.forecasting.constants import ForecastGranularity
from app.modules.forecasting.models import ReferenceSeries
from app.modules.forecasting.schemas import Provenance, SeriesInfo

PLATFORM_REF = "platform:collected_weight_kg"
REFERENCE_PREFIX = "reference:"
PLATFORM_LABEL = (
    "Platform data: weekly weight recorded by completed collection tasks in this system"
)


@dataclass
class SeriesData:
    info: SeriesInfo
    periods: list[dt.date]
    values: list[float]
    interpolated: list[bool]


def is_reference(ref: str) -> bool:
    return ref.startswith(REFERENCE_PREFIX)


def _monday(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def _platform(db: Session, today: dt.date | None = None) -> SeriesData:
    rows = collection.weekly_collected_weight_kg(db)
    last_complete = _monday(today or dt.datetime.now(dt.UTC).date()) - dt.timedelta(days=7)
    totals = {week: float(total) for week, total in rows if week <= last_complete}
    periods: list[dt.date] = []
    values: list[float] = []
    if totals:
        week = min(totals)
        while week <= last_complete:
            periods.append(week)
            values.append(totals.get(week, 0.0))
            week += dt.timedelta(days=7)
    info = SeriesInfo(
        ref=PLATFORM_REF,
        name="Collected weight (platform)",
        data_kind="platform",
        label=PLATFORM_LABEL,
        unit=QuantityUnit.KILOGRAM,
        granularity=ForecastGranularity.WEEK,
        points=len(values),
        first_period=periods[0] if periods else None,
        last_period=periods[-1] if periods else None,
        interpolated_points=0,
    )
    return SeriesData(info, periods, values, [False] * len(values))


def _reference_info(series: ReferenceSeries, interpolated: int) -> SeriesInfo:
    return SeriesInfo(
        ref=REFERENCE_PREFIX + series.key,
        name=series.name,
        data_kind="public_reference",
        label=f"Public reference data ({series.country}): not produced by this platform",
        unit=series.unit,
        granularity=series.granularity,
        points=series.point_count,
        first_period=series.first_period,
        last_period=series.last_period,
        interpolated_points=interpolated,
        provenance=Provenance(
            source_url=series.source_url,
            source_commit=series.source_commit,
            licence_note=series.licence_note,
            processing_note=series.processing_note,
        ),
    )


def load_series(db: Session, ref: str, *, today: dt.date | None = None) -> SeriesData:
    if ref == PLATFORM_REF:
        return _platform(db, today)
    if is_reference(ref):
        key = ref[len(REFERENCE_PREFIX) :]
        series = repository.get_reference_series(db, key)
        if series is not None:
            points = repository.reference_points(db, series.id)
            flags = [p.is_interpolated for p in points]
            return SeriesData(
                _reference_info(series, sum(flags)),
                [p.period_start for p in points],
                [float(p.value) for p in points],
                flags,
            )
    raise NotFoundError("Unknown series")


def list_series(db: Session) -> list[SeriesInfo]:
    out = [_platform(db).info]
    for row in repository.list_reference_series(db):
        out.append(_reference_info(row, repository.interpolated_count(db, row.id)))
    return out
