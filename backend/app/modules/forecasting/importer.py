"""Import of a public reference series (operator command; never an API endpoint).

Reads the git-ignored, pinned checkout of the public dataset through ``ml.time_series.data``,
applies the same weekly aggregation and completeness rule used by the benchmark, and stores the
result with its provenance. A series is refused when more than a quarter of its weeks had to be
interpolated.
"""

from __future__ import annotations

import decimal
import importlib
from typing import Any

from sqlalchemy.orm import Session

from app.common.enums import QuantityUnit
from app.core.exceptions import AppError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.forecasting import repository
from app.modules.forecasting.constants import ForecastGranularity
from app.modules.forecasting.models import ReferenceSeries

MAX_INTERPOLATED_FRACTION = 0.25


class ReferenceImportError(AppError):
    status_code = 400
    code = "reference_import_failed"


def import_reference_series(db: Session, key: str, *, context: RequestContext) -> ReferenceSeries:
    try:
        data: Any = importlib.import_module("ml.time_series.data")
    except ModuleNotFoundError as exc:
        raise ReferenceImportError("The ml.time_series package is not installed") from exc
    if key in data.EXCLUDED:
        raise ReferenceImportError(f"Series {key!r} is excluded: {data.EXCLUDED[key]}")
    if key not in data.SERIES:
        raise ReferenceImportError(f"Unknown series {key!r}; choose one of {sorted(data.SERIES)}")
    try:
        data.verify_pinned_commit()
        daily, audit_info = data.load_daily(key)
    except (OSError, RuntimeError) as exc:
        raise ReferenceImportError(f"The pinned dataset checkout is not available: {exc}") from exc
    weekly = data.weekly(daily, key)
    filled = weekly.n_filled
    if filled / len(weekly.values) > MAX_INTERPOLATED_FRACTION:
        raise ReferenceImportError(
            f"Series {key!r} rejected: {filled} of {len(weekly.values)} weeks would be interpolated"
        )
    name, country = data.SERIES[key][2], data.SERIES[key][3]
    note = (
        f"Daily weighbridge/collection records summed per ISO week (Monday start). "
        f"{weekly.rule}. {audit_info.non_positive} non-positive rows dropped; {filled} of "
        f"{len(weekly.values)} weeks interpolated (flagged) for model fitting."
    )
    series = repository.replace_reference_series(
        db,
        fields={
            "key": key,
            "name": name,
            "country": country,
            "unit": QuantityUnit.KILOGRAM,
            "granularity": ForecastGranularity.WEEK,
            "source_url": data.SOURCE["url"],
            "source_commit": data.SOURCE["commit"],
            "licence_note": data.SOURCE["licence_note"],
            "processing_note": note,
            "first_period": weekly.week_start[0],
            "last_period": weekly.week_start[-1],
            "point_count": len(weekly.values),
        },
        points=[
            (day, decimal.Decimal(repr(round(float(value), 3))), not bool(ok))
            for day, value, ok in zip(
                weekly.week_start, weekly.values, weekly.complete, strict=True
            )
        ],
    )
    audit.record(
        db,
        action="reference_series.imported",
        entity_type="reference_series",
        entity_id=series.id,
        context=context,
        changes={"key": key, "points": len(weekly.values), "interpolated": filled},
    )
    db.commit()
    return series
