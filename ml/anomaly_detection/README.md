# Anomaly detection

**Status:** implemented, but not in this directory. The detector is the robust-score rule in [`ml/time_series/algorithms.py`](../time_series/algorithms.py), run by `backend/app/modules/anomaly_detection` and `ml/time_series/benchmark.py`. The empty `data/`, `training/`, `inference/` and `evaluation/` folders here are kept only because the canonical structure check requires them.

## Contract
- **Input:** weekly weight series (kg).
- **Output:** an alert with the observed value, the expected value (median baseline: the same week in earlier years when enough history exists, otherwise the previous three weeks), the threshold, a severity (3.5 warning, 5 critical), the detector name and version and a required human-readable explanation (database CHECK).
- **Validation:** there are no incident labels in the public data, so **no precision or recall is claimed**. The detector is tested on injected spikes only, which shows it can detect a spike, not that it finds real incidents. Alerts are called "suspected anomalies" and a human records the outcome (acknowledged, resolved, false positive).
