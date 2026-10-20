# Forecasting API

Base path `/api/v1/forecasting`. Bearer authentication; standard error envelope. Reading needs `forecasting:read`, running a forecast `forecasting:run` (managers and administrators).

| Method and path | Purpose |
|---|---|
| `GET /forecasting/series` | Series that can be forecast, with kind, label and provenance |
| `GET /forecasting/series/history?series=<ref>` | Weekly history of one series (interpolated weeks flagged) |
| `POST /forecasting/forecasts` | Compute (and by default store) a weekly forecast (`201`) |
| `GET /forecasting/forecasts/latest?series=<ref>` | The most recently stored forecast for a series |

## Series: two kinds, never mixed

| `ref` | `data_kind` | Meaning |
|---|---|---|
| `platform:collected_weight_kg` | `platform` | Weekly kg recorded by completed collection tasks **in this system**. Runs from the first week with data to the last *complete* week (the current week is excluded). A week without collection is a true zero. |
| `reference:<key>` | `public_reference` | A public dataset imported with provenance (`python -m app.cli import-reference-series --key austin`). **Not produced by this platform.** Responses carry `label`, `provenance.source_url`, `source_commit`, `licence_note` and `processing_note`. |

Every response that involves a series includes a `label` the UI must display next to it.

## Forecasting

Request: `{"series": "<ref>", "horizon_weeks": 1..12 (default 4), "save": true}`. Unknown fields are `422`.

* `422 insufficient_history` when the series has fewer than **26 complete weeks**. `error.details[0]` carries `available_weeks` and `required_weeks`. Nothing is computed or stored.
* The model is chosen by a rolling-origin backtest over the most recent history: each origin refits on earlier weeks only, candidates are `naive`, `moving_average`, `ses`, `holt_damped`, `seasonal_naive` (52 weeks, needs > 52 weeks) and `holt_winters` (needs ≥ 104 weeks). The lowest mean absolute error wins; a model within 1% of the best is replaced by the simplest such model.
* The response contains the forecast points (`predicted`, 80% `lower`/`upper`, never below 0), the model and its fitted parameters, **backtest evidence** (`candidate_mae`, `selected_mae`, `naive_mae`, `mae_vs_naive`, `beats_naive`) and `caveats`. If no model beats repeating the last week, a caveat says so.
* The interval is approximate (it is derived from the in-sample error spread). On four public benchmark series its observed coverage ranged from 59% to 85% (`docs/ml/dataset-research/experiments/time-series-results.json`); a caveat states this.
* `save=true` stores one `forecast_results` row per week (metric = series ref, `model_name`, `model_version` = engine version `ts-1.0.0`, `generated_at`) and writes the audit entry `forecast.generated`.
* `503 forecast_engine_unavailable` if the algorithm package is not installed beside the backend (the Docker image ships `ml/time_series/algorithms.py`). No number is ever invented.

## What this is not

A forecast is a statistical extrapolation of past weekly totals. It does not know about closures, campaigns, weather or policy. It is not a fill-level (sensor) forecast: the platform has no bin sensors, so none is offered.

## Audit events

`forecast.generated`, `reference_series.imported` (CLI).
