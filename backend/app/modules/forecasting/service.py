"""Forecasting use cases. Reading needs ``forecasting:read``; running needs ``forecasting:run``."""

from __future__ import annotations

import datetime as dt
import decimal
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.common.enums import QuantityUnit
from app.core.exceptions import AppError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.forecasting import engine, repository, series
from app.modules.forecasting.constants import ForecastGranularity
from app.modules.forecasting.models import ForecastResult
from app.modules.forecasting.schemas import (
    BacktestEvidence,
    ForecastOut,
    ForecastPoint,
    ForecastRequest,
    ModelInfo,
    SeriesHistory,
    SeriesInfo,
    SeriesPointOut,
    StoredForecastOut,
)

SEASON_WEEKS = 52
MIN_WEEKS = 26  # fewer complete weeks than this and nothing is forecast
INTERVAL_LEVEL = 0.8
MAX_BACKTEST_ORIGINS = 12
MIN_HISTORY = 12  # same floor the algorithms use for the first backtest origin
_CENT = decimal.Decimal("0.001")

# Empirical 80%-interval coverage on four public series (docs/ml/dataset-research/experiments/
# time-series-results.json): 0.594 (Dehiwala) to 0.849 (Austin).
INTERVAL_NOTE = (
    "The 80% range is approximate: on four public benchmark series its observed coverage "
    "ranged from 59% to 85%."
)


class InsufficientHistoryError(AppError):
    status_code = 422
    code = "insufficient_history"


def list_series(db: Session) -> list[SeriesInfo]:
    return series.list_series(db)


def get_history(db: Session, ref: str) -> SeriesHistory:
    data = series.load_series(db, ref)
    return SeriesHistory(
        series=data.info,
        points=[
            SeriesPointOut(period_start=p, value=v, interpolated=i)
            for p, v, i in zip(data.periods, data.values, data.interpolated, strict=True)
        ],
    )


def _dec(value: float) -> decimal.Decimal:
    return decimal.Decimal(repr(float(value))).quantize(_CENT, rounding=decimal.ROUND_HALF_UP)


def forecast_series(
    db: Session,
    ref: str,
    horizon: int,
    *,
    today: dt.date | None = None,
) -> tuple[SeriesInfo, ModelInfo, BacktestEvidence, list[ForecastPoint], list[str]]:
    """Compute (not persist) a forecast. Raises ``InsufficientHistoryError`` rather than guess."""
    data = series.load_series(db, ref, today=today)
    n = len(data.values)
    if n < MIN_WEEKS:
        raise InsufficientHistoryError(
            f"At least {MIN_WEEKS} complete weeks of history are needed to forecast; "
            f"this series has {n}.",
            details=[{"available_weeks": n, "required_weeks": MIN_WEEKS}],
        )
    alg: Any = engine.algorithms()
    y = np.asarray(data.values, dtype=np.float64)
    chosen, errors = alg.select_model(y, horizon=horizon, season=SEASON_WEEKS)
    fit = alg.fit_forecast(chosen, y, horizon, SEASON_WEEKS)
    lower, upper = alg.prediction_interval(fit, level=INTERVAL_LEVEL)

    last = data.periods[-1]
    points = [
        ForecastPoint(
            period_start=last + dt.timedelta(days=7 * (i + 1)),
            period_end=last + dt.timedelta(days=7 * (i + 2)),
            predicted=_dec(max(float(fit.forecast[i]), 0.0)),
            lower=_dec(max(float(lower[i]), 0.0)),
            upper=_dec(max(float(upper[i]), 0.0)),
        )
        for i in range(horizon)
    ]
    first_origin = max(MIN_HISTORY, n - MAX_BACKTEST_ORIGINS * horizon)
    origins = len(range(first_origin, n - horizon + 1, horizon))
    selected_mae = errors.get(chosen)
    naive_mae = errors.get("naive")
    ratio = selected_mae / naive_mae if selected_mae is not None and naive_mae else None
    backtest = BacktestEvidence(
        horizon_weeks=horizon,
        origins=origins if errors else 0,
        candidate_mae={k: float(v) for k, v in errors.items()},
        selected_mae=selected_mae,
        naive_mae=naive_mae,
        mae_vs_naive=ratio,
        beats_naive=None if ratio is None else ratio < 1.0,
    )
    selection = (
        "Lowest mean absolute error in a rolling-origin backtest on the most recent history "
        "(each origin refit on earlier weeks only); ties go to the simpler model."
        if errors
        else "Fallback to the naive model: too little history to compare models."
    )
    caveats = [
        "Statistical extrapolation of past weekly totals. It cannot anticipate closures, "
        "campaigns, weather or policy changes.",
        INTERVAL_NOTE,
    ]
    if data.info.data_kind == "public_reference":
        caveats.append("This is public reference data, not waste handled by this platform.")
    if chosen == "naive" and ratio is not None and ratio >= 1.0:
        caveats.append("No candidate beat repeating the last week on recent history.")
    if data.info.interpolated_points:
        caveats.append(
            f"{data.info.interpolated_points} weeks with too few observed days were "
            "interpolated for fitting."
        )
    model = ModelInfo(
        name=chosen,
        engine_version=engine.ENGINE_VERSION,
        parameters={k: float(v) for k, v in fit.params.items()},
        selection=selection,
    )
    return data.info, model, backtest, points, caveats


def run_forecast(
    db: Session, principal: Principal, payload: ForecastRequest, *, context: RequestContext
) -> ForecastOut:
    info, model, backtest, points, caveats = forecast_series(
        db, payload.series, payload.horizon_weeks
    )
    now = dt.datetime.now(dt.UTC)
    if payload.save:
        repository.add_forecast_rows(
            db,
            [
                ForecastResult(
                    metric=info.ref,
                    unit=QuantityUnit(info.unit),
                    granularity=ForecastGranularity.WEEK,
                    period_start=dt.datetime.combine(p.period_start, dt.time(), dt.UTC),
                    period_end=dt.datetime.combine(p.period_end, dt.time(), dt.UTC),
                    predicted_value=p.predicted,
                    lower_bound=p.lower,
                    upper_bound=p.upper,
                    model_name=model.name,
                    model_version=model.engine_version,
                    generated_at=now,
                )
                for p in points
            ],
        )
        audit.record(
            db,
            action="forecast.generated",
            entity_type="forecast_series",
            actor_id=principal.user_id,
            context=context,
            changes={
                "series": info.ref,
                "model": model.name,
                "horizon_weeks": payload.horizon_weeks,
                "beats_naive": backtest.beats_naive,
            },
        )
        db.commit()
    return ForecastOut(
        series=info,
        model=model,
        backtest=backtest,
        interval_level=INTERVAL_LEVEL,
        points=points,
        caveats=caveats,
        generated_at=now,
        saved=payload.save,
    )


def latest_stored(db: Session, ref: str) -> StoredForecastOut:
    data = series.load_series(db, ref)
    rows = repository.latest_forecast(db, ref)
    return StoredForecastOut(
        series=data.info,
        generated_at=rows[0].generated_at if rows else None,
        model_name=rows[0].model_name if rows else None,
        model_version=rows[0].model_version if rows else None,
        points=[
            ForecastPoint(
                period_start=r.period_start.date(),
                period_end=r.period_end.date(),
                predicted=r.predicted_value,
                lower=r.lower_bound if r.lower_bound is not None else r.predicted_value,
                upper=r.upper_bound if r.upper_bound is not None else r.predicted_value,
            )
            for r in rows
        ],
    )
