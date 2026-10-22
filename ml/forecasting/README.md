# Forecasting

**Status:** implemented, but not in this directory. The algorithms live in [`ml/time_series/`](../time_series/) (`algorithms.py`: naive, seasonal naive, moving average, simple and damped exponential smoothing, Holt-Winters, the model-selection rule and the prediction interval; `data.py`: loading of the public reference series; `benchmark.py`: the evaluation). The backend adapter is `backend/app/modules/forecasting/engine.py`, which loads `ml.time_series.algorithms` by name. The empty `data/`, `training/`, `inference/` and `evaluation/` folders here are kept only because the canonical structure check requires them.

## Contract
- **Input:** weekly weight totals (kg) with consistent UTC week starts. The forecaster refuses fewer than 26 weeks (`422 insufficient_history`).
- **Output:** per future week `predicted_value`, an 80% interval, the unit, the model name and version, and the baseline forecast beside it (stored in `forecast_results`).
- **Baseline first:** a model is used only if it beat the naive baseline on the development segment; the test segment is scored once.
- **Evaluation:** chronological split (first 70% of weeks development, last 30% test), rolling origin, horizon 4 weeks. Command: `PYTHONPATH=. python -m ml.time_series.benchmark`. Results: `docs/ml/dataset-research/experiments/time-series-results.json` and `docs/academic/results.md` section 4 (Holt-Winters beat naive on 2 of 4 usable public series; intervals were not reliable on the short ones).
- Protocol: `docs/ml/evaluation-protocol.md`.
