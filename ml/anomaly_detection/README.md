# Anomaly detection

**Status:** not started.

## Contract (target)
- **Input:** operational metrics with timestamps and units (for example waste collected per facility per day, task completion times).
- **Output:** an alert with `metric`, `observed_value`, `expected_value`, `threshold_value`, `severity`, detector name/version and a required human-readable `explanation`.
- **Baseline first:** a documented statistical rule (for example robust z-score or rolling-median deviation with explicit thresholds) before any learned detector.
- **Validation:** against known cases or explicitly labelled simulated cases; simulated data is always labelled as such and is never presented as real operations.
