"""Forecasting + anomaly benchmark on public municipal-waste series.

    PYTHONPATH=. python -m ml.time_series.benchmark

Protocol (declared before looking at results)
* Weekly totals (``data.weekly``). A series is used only when <= 25% of its weeks had to be
  interpolated; others are excluded and reported.
* Chronological split: first 70% of weeks = development, last 30% = test.
* Model selection (``select_model``) sees the development weeks only.
* Test: rolling origin, horizon 4 weeks, refit every 4 weeks on all weeks before the origin;
  only COMPLETE (non-interpolated) test weeks are scored.
* Baseline to beat: ``naive``; also reported seasonal-naive and moving average.
* Intervals: nominal 80%; empirical coverage is reported.
* Anomalies: the data has no incident labels, so recall is measured on INJECTED anomalies
  (x2.5 spikes and x0.3 drops at seeded positions). This measures sensitivity to known
  synthetic deviations, not detection of real incidents. The alert rate on the clean series is
  an upper bound on false alarms (some alerts there may be genuine irregularities).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ml.time_series import algorithms as alg
from ml.time_series.data import EXCLUDED, SERIES, WeeklySeries, load_daily, weekly

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "ml" / "dataset-research" / "experiments" / "time-series-results.json"
SEASON = 52
HORIZON = 4
MAX_FILLED_FRACTION = 0.25
SEED = 42


def evaluate_forecasts(ws: WeeklySeries) -> dict[str, Any]:
    y = ws.values
    split = int(len(y) * 0.7)
    scale = alg.mase_scale(y[:split])
    selected, dev_errors = alg.select_model(y[:split], horizon=HORIZON, season=SEASON)
    names = alg.candidate_models(split, SEASON)
    results: dict[str, Any] = {}
    for name in [*names, "selected"]:
        model = selected if name == "selected" else name
        actual, pred, target = alg.rolling_origin(
            y, model, first_origin=split, horizon=HORIZON, step=HORIZON, season=SEASON
        )
        keep = ws.complete[target]
        results[name] = {
            "model": model,
            **alg.score(actual[keep], pred[keep], scale),
            "n_scored": int(keep.sum()),
        }
    # interval calibration for the selected model
    covered, total = 0, 0
    for origin in range(split, len(y) - HORIZON + 1, HORIZON):
        fit = alg.fit_forecast(selected, y[:origin], HORIZON, SEASON)
        lo, hi = alg.prediction_interval(fit, level=0.8)
        for h in range(HORIZON):
            if ws.complete[origin + h]:
                total += 1
                covered += int(lo[h] <= y[origin + h] <= hi[h])
    naive_mae = results["naive"]["mae"]
    return {
        "weeks": len(y),
        "weeks_interpolated": ws.n_filled,
        "first_week": ws.week_start[0].isoformat(),
        "last_week": ws.week_start[-1].isoformat(),
        "split_week": ws.week_start[split].isoformat(),
        "n_development": split,
        "n_test_weeks": len(y) - split,
        "selected_on_development": selected,
        "development_backtest_mae": dev_errors,
        "models": results,
        "selected_vs_naive_mae_ratio": results["selected"]["mae"] / naive_mae,
        "beats_naive": results["selected"]["mae"] < naive_mae,
        "interval_80_empirical_coverage": covered / total if total else None,
        "interval_n": total,
    }


def inject(y: np.ndarray, rng: np.random.Generator, lo: int) -> tuple[np.ndarray, dict[int, str]]:
    out, truth = y.copy(), {}
    candidates = list(range(lo, len(y)))
    rng.shuffle(candidates)
    for idx in candidates:
        if len(truth) >= 10:
            break
        if all(abs(idx - j) >= 8 for j in truth):
            kind = "spike" if len(truth) % 2 == 0 else "drop"
            out[idx] = y[idx] * (2.5 if kind == "spike" else 0.3)
            truth[idx] = kind
    return out, truth


def evaluate_anomalies(ws: WeeklySeries) -> dict[str, Any]:
    y = ws.values
    lo = int(len(y) * 0.5)
    season = alg.anomaly_season(len(y))
    clean = alg.detect_anomalies(y, season=season)
    rng = np.random.default_rng(SEED)
    injected, truth = inject(y, rng, lo)
    found = alg.detect_anomalies(injected, season=season)
    flagged = {p.index: p for p in found}
    hit = [i for i in truth if i in flagged]
    false_alerts = [p for p in found if p.index not in truth]
    warmup = max(2 * season, alg.MIN_HISTORY)
    return {
        "season_used": season,
        "scored_weeks": len(y) - warmup,
        "alerts_on_clean_series": len(clean),
        "clean_alert_rate_per_100_weeks": 100 * len(clean) / max(len(y) - warmup, 1),
        "injected": len(truth),
        "injected_detected": len(hit),
        "injected_recall": len(hit) / len(truth) if truth else None,
        "injected_critical": sum(1 for i in hit if flagged[i].severity == "critical"),
        "alerts_not_injected": len(false_alerts),
        "note": "injected anomalies are synthetic; this is sensitivity, not real-incident recall",
    }


def main() -> int:
    report: dict[str, Any] = {
        "protocol": {
            "granularity": "weekly totals (Monday start)",
            "season_weeks": SEASON,
            "horizon_weeks": HORIZON,
            "split": "chronological 70% development / 30% test",
            "max_interpolated_fraction": MAX_FILLED_FRACTION,
            "seed": SEED,
        },
        "excluded": dict(EXCLUDED),
        "series": {},
    }
    for key, (_, _, name, country) in SERIES.items():
        daily, audit = load_daily(key)
        ws = weekly(daily, key)
        info: dict[str, Any] = {
            "name": name,
            "country": country,
            "rows": audit.rows,
            "non_positive_rows_dropped": audit.non_positive,
            "unparseable_rows": audit.unparseable,
            "observed_days": audit.days,
            "day_coverage": round(audit.coverage, 3),
            "weekday_presence": audit.weekday_presence,
            "week_rule": ws.rule,
        }
        if ws.n_filled / len(ws.values) > MAX_FILLED_FRACTION:
            info["excluded"] = (
                f"{ws.n_filled} of {len(ws.values)} weeks interpolated "
                f"(> {int(MAX_FILLED_FRACTION * 100)}% gate)"
            )
        else:
            info["forecast"] = evaluate_forecasts(ws)
            info["anomaly"] = evaluate_anomalies(ws)
        report["series"][key] = info
        print(
            key,
            info.get("excluded")
            or f"selected {info['forecast']['selected_on_development']}, "
            f"MAE/naive {info['forecast']['selected_vs_naive_mae_ratio']:.3f}",
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
