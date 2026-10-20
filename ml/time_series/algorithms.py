"""Forecasting baselines and a residual-based anomaly detector (pure numpy, no training service).

Everything here is deterministic and works on a regular series (equal spacing, no gaps: the
caller aggregates and fills/flags gaps). Parameters are chosen by in-sample one-step squared
error over a small fixed grid, so a fit never looks at the data it will be scored on.

Models
    naive              last observation
    seasonal_naive     the observation one season ago
    moving_average     mean of the last ``window`` observations
    ses                simple exponential smoothing
    holt_damped        damped-trend exponential smoothing
    holt_winters       additive trend + additive seasonality (needs two full seasons)
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Arr = NDArray[np.float64]
MIN_HISTORY = 12  # below this nothing is forecast ("insufficient history")


@dataclass(frozen=True)
class Fit:
    model: str
    params: dict[str, float]
    forecast: Arr  # (horizon,)
    residuals: Arr  # in-sample one-step errors, y_t - yhat_t


def _clean(y: Arr) -> Arr:
    values = np.asarray(y, dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("series must be one-dimensional and finite (fill or drop gaps first)")
    return values


def naive(y: Arr, horizon: int, **_: float) -> Fit:
    y = _clean(y)
    return Fit("naive", {}, np.repeat(y[-1], horizon), y[1:] - y[:-1])


def seasonal_naive(y: Arr, horizon: int, *, season: int, **_: float) -> Fit:
    y = _clean(y)
    if len(y) < season + 1:
        raise ValueError("seasonal_naive needs more than one season of history")
    forecast = np.array([y[len(y) - season + (h % season)] for h in range(horizon)])
    return Fit("seasonal_naive", {"season": float(season)}, forecast, y[season:] - y[:-season])


def moving_average(y: Arr, horizon: int, *, window: int = 4, **_: float) -> Fit:
    y = _clean(y)
    window = min(window, len(y))
    resid = np.array([y[t] - y[max(0, t - window) : t].mean() for t in range(1, len(y))])
    return Fit(
        "moving_average", {"window": float(window)}, np.repeat(y[-window:].mean(), horizon), resid
    )


def _ses_run(y: Arr, alpha: float) -> tuple[float, Arr]:
    level = float(y[0])
    resid = np.empty(len(y) - 1)
    for t in range(1, len(y)):
        resid[t - 1] = y[t] - level
        level += alpha * (y[t] - level)
    return level, resid


def ses(y: Arr, horizon: int, **_: float) -> Fit:
    y = _clean(y)
    best = min(
        ((a, *_ses_run(y, a)) for a in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9)),
        key=lambda r: float(np.sum(r[2] ** 2)),
    )
    return Fit("ses", {"alpha": best[0]}, np.repeat(best[1], horizon), best[2])


def _holt_run(y: Arr, alpha: float, beta: float, phi: float) -> tuple[float, float, Arr]:
    level, trend = float(y[0]), float(y[1] - y[0])
    resid = np.empty(len(y) - 1)
    for t in range(1, len(y)):
        pred = level + phi * trend
        resid[t - 1] = y[t] - pred
        new_level = pred + alpha * (y[t] - pred)
        trend = phi * trend + beta * (new_level - level - phi * trend)
        level = new_level
    return level, trend, resid


def holt_damped(y: Arr, horizon: int, **_: float) -> Fit:
    y = _clean(y)
    if len(y) < 3:
        raise ValueError("holt_damped needs at least 3 observations")
    grid = itertools.product((0.2, 0.4, 0.6, 0.8), (0.01, 0.05, 0.15), (0.8, 0.9, 0.98))
    best = min(
        ((a, b, p, *_holt_run(y, a, b, p)) for a, b, p in grid),
        key=lambda r: float(np.sum(r[5] ** 2)),
    )
    a, b, phi, level, trend, resid = best
    steps = np.cumsum(phi ** np.arange(1, horizon + 1))
    return Fit("holt_damped", {"alpha": a, "beta": b, "phi": phi}, level + steps * trend, resid)


def _hw_run(
    y: Arr, m: int, alpha: float, beta: float, gamma: float
) -> tuple[float, float, Arr, Arr]:
    level = float(y[:m].mean())
    trend = float((y[m : 2 * m].mean() - y[:m].mean()) / m)
    seasonal = (y[:m] - level).astype(np.float64)
    resid = np.empty(len(y) - m)
    for t in range(m, len(y)):
        s = seasonal[t % m]
        pred = level + trend + s
        resid[t - m] = y[t] - pred
        new_level = alpha * (y[t] - s) + (1 - alpha) * (level + trend)
        trend = beta * (new_level - level) + (1 - beta) * trend
        seasonal[t % m] = gamma * (y[t] - new_level) + (1 - gamma) * s
        level = new_level
    return level, trend, seasonal, resid


def holt_winters(y: Arr, horizon: int, *, season: int, **_: float) -> Fit:
    y = _clean(y)
    if len(y) < 2 * season:
        raise ValueError("holt_winters needs two full seasons of history")
    grid = itertools.product((0.1, 0.3, 0.5), (0.01, 0.05), (0.05, 0.2, 0.4))
    best = min(
        ((a, b, g, *_hw_run(y, season, a, b, g)) for a, b, g in grid),
        key=lambda r: float(np.sum(r[6] ** 2)),
    )
    a, b, g, level, trend, seasonal, resid = best
    n = len(y)
    forecast = np.array(
        [level + (h + 1) * trend + seasonal[(n + h) % season] for h in range(horizon)]
    )
    return Fit(
        "holt_winters",
        {"alpha": a, "beta": b, "gamma": g, "season": float(season)},
        forecast,
        resid,
    )


MODELS: dict[str, Callable[..., Fit]] = {
    "naive": naive,
    "seasonal_naive": seasonal_naive,
    "moving_average": moving_average,
    "ses": ses,
    "holt_damped": holt_damped,
    "holt_winters": holt_winters,
}
NEEDS_SEASON = {"seasonal_naive", "holt_winters"}
# Simplest first: ties in backtest error resolve towards the simpler model.
COMPLEXITY = list(MODELS)


def candidate_models(n: int, season: int) -> list[str]:
    out = ["naive", "moving_average", "ses"]
    if n >= 3:
        out.append("holt_damped")
    if n >= season + 1:
        out.append("seasonal_naive")
    if n >= 2 * season:
        out.append("holt_winters")
    return out


def fit_forecast(model: str, y: Arr, horizon: int, season: int) -> Fit:
    return MODELS[model](y, horizon, season=season)


# ------------------------------------------------------------------------ evaluation
def mase_scale(y: Arr) -> float:
    """In-sample mean absolute one-step naive error (the MASE denominator)."""
    scale = float(np.mean(np.abs(np.diff(y))))
    return scale if scale > 0 else 1.0


def rolling_origin(
    y: Arr, model: str, *, first_origin: int, horizon: int, step: int, season: int
) -> tuple[Arr, Arr, Arr]:
    """Refit at each origin using ONLY data before it; return (actual, forecast, target_index)
    flattened over horizons. Chronological: nothing after an origin is ever seen."""
    actual, predicted, origins = [], [], []
    for origin in range(first_origin, len(y) - horizon + 1, step):
        fit = fit_forecast(model, y[:origin], horizon, season)
        actual.extend(y[origin : origin + horizon])
        predicted.extend(fit.forecast)
        origins.extend(range(origin, origin + horizon))
    return np.array(actual), np.array(predicted), np.array(origins)


def score(actual: Arr, predicted: Arr, scale: float) -> dict[str, float]:
    err = predicted - actual
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "wape": float(np.sum(np.abs(err)) / max(np.sum(np.abs(actual)), 1e-12)),
        "mase": float(np.mean(np.abs(err)) / scale),
        "bias": float(np.mean(err)),
    }


def select_model(
    y: Arr, *, horizon: int, season: int, max_origins: int = 12
) -> tuple[str, dict[str, float]]:
    """Pick the model with the lowest rolling-origin MAE on the tail of ``y`` (history only)."""
    y = _clean(y)
    names = candidate_models(len(y) - max_origins * horizon, season) or ["naive"]
    first = max(MIN_HISTORY, len(y) - max_origins * horizon)
    errors: dict[str, float] = {}
    for name in names:
        try:
            a, p, _ = rolling_origin(
                y, name, first_origin=first, horizon=horizon, step=horizon, season=season
            )
        except ValueError:
            continue
        if len(a):
            errors[name] = float(np.mean(np.abs(a - p)))
    if not errors:
        return "naive", {}
    best = min(errors.values())
    for name in COMPLEXITY:  # simplest model within 1% of the best
        if name in errors and errors[name] <= best * 1.01:
            return name, errors
    raise AssertionError("unreachable")  # pragma: no cover


def prediction_interval(fit: Fit, *, level: float = 0.8) -> tuple[Arr, Arr]:
    """Symmetric interval from the in-sample one-step residual spread, widened by sqrt(h).

    This is an approximation (it assumes roughly stationary, uncorrelated errors); the
    benchmark reports its empirical coverage so it is never presented as exact.
    """
    resid = fit.residuals
    sigma = 1.4826 * float(np.median(np.abs(resid - np.median(resid)))) if len(resid) else 0.0
    z = {0.5: 0.674, 0.8: 1.282, 0.9: 1.645, 0.95: 1.960}[level]
    width = z * sigma * np.sqrt(np.arange(1, len(fit.forecast) + 1))
    return fit.forecast - width, fit.forecast + width


# ------------------------------------------------------------------------ anomalies
WEEKS_PER_YEAR = 52


def anomaly_season(n_weeks: int) -> int:
    """Yearly comparison once three years of weeks exist; otherwise a level-based rule (the
    median of the last three weeks), because a yearly baseline cannot be formed yet."""
    return WEEKS_PER_YEAR if n_weeks >= 3 * WEEKS_PER_YEAR else 1


@dataclass(frozen=True)
class AnomalyPoint:
    index: int
    observed: float
    expected: float
    score: float  # robust z of the one-step forecast error
    tolerance: float  # |error| needed to reach the warning level (warn_z x robust scale)
    severity: str  # "warning" | "critical"


def detect_anomalies(
    y: Arr, *, season: int, warn_z: float = 3.5, crit_z: float = 5.0, warmup: int | None = None
) -> list[AnomalyPoint]:
    """Flag points whose one-step-ahead forecast error is extreme relative to the PAST errors.

    The one-step expectation is the MEDIAN of the same position in up to three previous seasons
    (robust to one earlier outlier). The error scale is the MAD of EARLIER errors only, so
    nothing after ``t`` influences the decision at ``t``. This flags *suspected* anomalies in the
    data; it does not know whether the cause is a real incident, a data-entry error or a
    holiday.
    """
    y = _clean(y)
    warmup = warmup if warmup is not None else max(2 * season, MIN_HISTORY)
    expected = np.full(len(y), np.nan)
    for t in range(season, len(y)):
        lags = [y[t - k * season] for k in (1, 2, 3) if t - k * season >= 0]
        expected[t] = float(np.median(lags))
    errors = y - expected
    out: list[AnomalyPoint] = []
    for t in range(warmup, len(y)):
        past = errors[season:t]
        past = past[np.isfinite(past)]
        if len(past) < MIN_HISTORY:
            continue
        mad = 1.4826 * float(np.median(np.abs(past - np.median(past))))
        if mad <= 0:
            continue
        z = float((errors[t] - np.median(past)) / mad)
        if abs(z) >= warn_z:
            out.append(
                AnomalyPoint(
                    t,
                    float(y[t]),
                    float(expected[t]),
                    z,
                    warn_z * mad,
                    "critical" if abs(z) >= crit_z else "warning",
                )
            )
    return out
