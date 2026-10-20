"""Forecasting / anomaly algorithms: known values, no look-ahead, gap handling."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from ml.time_series import algorithms as alg
from ml.time_series.data import weekly


def seasonal_series(
    n: int = 160, season: int = 12, trend: float = 0.5, noise: float = 0.0
) -> np.ndarray:
    t = np.arange(n)
    rng = np.random.default_rng(0)
    return 100 + trend * t + 20 * np.sin(2 * np.pi * t / season) + rng.normal(0, noise, n)


def test_naive_and_seasonal_naive_known_values() -> None:
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert alg.naive(y, 3).forecast.tolist() == [6.0, 6.0, 6.0]
    # season 3: the next values repeat the last three observations
    assert alg.seasonal_naive(y, 5, season=3).forecast.tolist() == [4.0, 5.0, 6.0, 4.0, 5.0]
    assert alg.moving_average(y, 2, window=3).forecast.tolist() == [5.0, 5.0]


def test_inputs_must_be_finite_and_one_dimensional() -> None:
    with pytest.raises(ValueError):
        alg.naive(np.array([1.0, np.nan, 3.0]), 2)
    with pytest.raises(ValueError):
        alg.naive(np.ones((3, 2)), 2)
    with pytest.raises(ValueError, match="two full seasons"):
        alg.holt_winters(np.arange(10.0), 2, season=12)
    with pytest.raises(ValueError):
        alg.seasonal_naive(np.arange(5.0), 2, season=12)


def test_holt_winters_recovers_trend_and_seasonality() -> None:
    y = seasonal_series()
    fit = alg.holt_winters(y[:-12], 12, season=12)
    mae_hw = float(np.mean(np.abs(fit.forecast - y[-12:])))
    mae_naive = float(np.mean(np.abs(alg.naive(y[:-12], 12).forecast - y[-12:])))
    assert mae_hw < 3.0 and mae_hw < mae_naive / 4


def test_forecasts_are_deterministic() -> None:
    y = seasonal_series(noise=3.0)
    a = alg.fit_forecast("holt_winters", y, 8, 12)
    b = alg.fit_forecast("holt_winters", y.copy(), 8, 12)
    assert np.array_equal(a.forecast, b.forecast) and a.params == b.params


def test_rolling_origin_never_uses_the_future() -> None:
    y = seasonal_series(noise=2.0)
    first = 100
    base = alg.rolling_origin(y, "holt_winters", first_origin=first, horizon=4, step=4, season=12)
    changed = y.copy()
    changed[130:] += 1000.0  # corrupt everything after the 8th origin's training window
    other = alg.rolling_origin(
        changed, "holt_winters", first_origin=first, horizon=4, step=4, season=12
    )
    early = base[2] < 130  # targets before the corrupted region start
    assert np.array_equal(base[1][early][:24], other[1][early][:24])  # same forecasts
    assert not np.array_equal(base[0], other[0])  # while the actuals differ


def test_select_model_prefers_seasonal_model_on_seasonal_data_and_naive_on_flat() -> None:
    chosen, errors = alg.select_model(seasonal_series(noise=1.0), horizon=4, season=12)
    assert chosen in {"seasonal_naive", "holt_winters"}
    assert errors[chosen] < errors["naive"]
    flat = np.full(80, 50.0)
    assert alg.select_model(flat, horizon=4, season=12)[0] == "naive"  # ties go to the simplest


def test_prediction_interval_widens_with_horizon_and_brackets_forecast() -> None:
    y = seasonal_series(noise=4.0)
    fit = alg.fit_forecast("holt_damped", y, 6, 12)
    lo, hi = alg.prediction_interval(fit, level=0.8)
    assert np.all(lo < fit.forecast) and np.all(hi > fit.forecast)
    assert np.all(np.diff(hi - lo) > 0)


def test_detects_injected_spike_and_drop_but_not_clean_noise() -> None:
    rng = np.random.default_rng(1)
    y = 100 + 10 * np.sin(2 * np.pi * np.arange(200) / 13) + rng.normal(0, 1.0, 200)
    assert alg.detect_anomalies(y, season=13) == []
    spiked = y.copy()
    spiked[150] *= 2.5
    spiked[170] *= 0.2
    found = {p.index: p for p in alg.detect_anomalies(spiked, season=13)}
    assert {150, 170} <= set(found)
    assert found[150].score > 0 > found[170].score
    assert found[150].severity == "critical"


def test_anomaly_decision_at_t_ignores_everything_after_t() -> None:
    rng = np.random.default_rng(2)
    y = 100 + rng.normal(0, 2, 160)
    y[120] = 300.0
    full = {p.index: p.score for p in alg.detect_anomalies(y, season=13)}
    truncated = {p.index: p.score for p in alg.detect_anomalies(y[:121], season=13)}
    assert 120 in full and 120 in truncated
    assert full[120] == truncated[120]


def test_constant_series_never_raises_or_alerts() -> None:
    assert alg.detect_anomalies(np.full(100, 5.0), season=7) == []


def test_weekly_marks_incomplete_weeks_and_interpolates_only_for_fitting() -> None:
    daily: dict[dt.date, float] = {}
    monday = dt.date(2024, 1, 1)
    for week in range(10):
        for day in range(5):  # Mon-Fri operating
            if week == 5 and day > 0:  # week 5 has a single day: incomplete
                continue
            daily[monday + dt.timedelta(weeks=week, days=day)] = 100.0
    series = weekly(daily, "t")
    assert series.operating_weekdays == [0, 1, 2, 3, 4]
    # boundary weeks are never complete; the interior short week is flagged and filled
    kept = series.complete.sum()
    assert series.n_filled >= 1 and kept >= 7
    assert np.allclose(series.values[series.complete], 500.0)
    assert np.all(np.isfinite(series.values))
    short = [i for i, ok in enumerate(series.complete) if not ok]
    assert all(
        series.values[i] == pytest.approx(500.0) for i in short
    )  # linear fill between equal neighbours
