# Forecasting

**Status:** not started.

## Contract (target)
- **Input:** historical observations with consistent UTC timestamps and explicit units (kg), aggregated per granularity (day/week/month) and optionally per facility or material category. Observations are read through backend service interfaces, not raw tables.
- **Output:** per future period: `predicted_value`, optional `lower_bound`/`upper_bound`, `unit`, model name and version (stored in `forecast_results`).
- **Baseline first:** a seasonal-naive or moving-average baseline is implemented and evaluated before any learned model; a learned model is adopted only if it beats the baseline on chronological evaluation.
- **Evaluation:** chronological split (train on the past, test on the future), stated horizon, MAE / RMSE / MAPE-or-sMAPE reported against the baseline. See `docs/ml/evaluation-protocol.md`.
