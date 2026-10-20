# Anomaly detection API

Base path `/api/v1/anomalies`. Bearer authentication; standard error envelope. Reading needs `anomalies:read`; scanning and handling alerts need `anomalies:manage` (managers and administrators).

| Method and path | Purpose |
|---|---|
| `GET /anomalies` | Paginated alerts (filter `status`, `severity`, `series`, `data_kind`; sort) |
| `GET /anomalies/{id}` | One alert |
| `POST /anomalies/scan` | Run the detector over a series and record new alerts |
| `POST /anomalies/{id}/acknowledge` | `open → acknowledged` |
| `POST /anomalies/{id}/resolve` | `open|acknowledged → resolved` |
| `POST /anomalies/{id}/false-positive` | `open|acknowledged → false_positive` |

## Wording: *suspected* anomalies

The detector compares a weekly total with that series' own history. It cannot know whether the cause is a real incident, a data-entry error, a holiday or a closure. Every alert's `explanation` ends with "Suspected anomaly, not a confirmed incident", and the scan response repeats this in `caveat`. `false_positive` exists so reviewers can record that a value was explained.

## Detector

For each week *t*: `expected` = the **median** of the same week in up to three previous years (when ≥ 156 weeks of history exist) or of the previous three weeks (shorter histories); the error `observed − expected` is divided by the robust scale (1.4826 × MAD) of **earlier** errors only (no look-ahead). Score ≥ 3.5 → `warning`; ≥ 5.0 → `critical`. Warm-up: 104 weeks (yearly rule) or 12 weeks (level rule); before that `422 insufficient_history`. Detector version `ts-1.0.0`.

* **Idempotent:** a week already alerted for the same series and detector is not duplicated (`already_recorded`).
* **No alerts on filled-in data:** weeks that were interpolated are never alerted.
* `lookback_weeks` (1–520, default 26) restricts which recent weeks may raise alerts.
* Alert fields: `observed_value`, `expected_value`, `threshold_value` (the deviation, in kg, needed to reach the warning level), `window_start`/`window_end`, `detector_name`, `detector_version`, `detected_at`.

## Platform vs public data

`data_kind` is `platform` for the platform's own series and `public_reference` for imported public series (`metric` starts with `reference:`). The list defaults to `data_kind=platform` so demonstration alerts never mix into operational ones.

## Lifecycle

`open → acknowledged → resolved`, or `open|acknowledged → false_positive`. `resolved` and `false_positive` are terminal; anything else is `409 invalid_alert_transition`. `note` (1–1000 characters, optional) is stored in the audit entry. Reviewing records who and when.

## Evidence and limits

The data has **no incident labels**, so detection quality on real incidents is unmeasured. The benchmark (`ml/time_series/benchmark.py`) reports sensitivity to *injected* anomalies and the alert rate on clean series; see `docs/ml/dataset-research/`. No precision or recall on real incidents is claimed.

## Audit events

`anomaly.scan`, `anomaly_alert.acknowledged`, `anomaly_alert.resolved`, `anomaly_alert.false_positive`.
