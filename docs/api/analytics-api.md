# Analytics API

Base path `/api/v1/analytics`. Read-only; requires `analytics:read` (managers and administrators). Every figure is computed from the database when requested; nothing is cached, estimated or seeded.

| Method and path | Parameters | Purpose |
|---|---|---|
| `GET /analytics/overview` | `window_days` 1–365 (default 30) | Operational snapshot |
| `GET /analytics/weekly-trend` | `weeks` 1–104 (default 12) | Weekly collected weight, completed tasks and submitted reports |

## Overview sections

* **reports**: total, submitted within the window, count per status.
* **collection**: tasks by status, open tasks (pending, assigned, in progress), **overdue** tasks (open with a past due time), tasks with a `collected` event in the window, collected weight in the window and in total.
* **fleet**: vehicles by status and the summed capacity of available or in-service vehicles.
* **facilities**: total and active.
* **incidents**: total, open, open and unassigned.
* **recovery**: only verified recovery records count; `recovery_rate` is `null` until there is verified input weight.
* **rewards**: ledger entries, users, net points and impact weight.
* **anomalies**: open suspected anomalies and how many are critical. A suspected anomaly is not a confirmed incident.
* **passports**: count per custody status.

Stock figures (current state) ignore the window; flow figures use it. The `basis` field states that no carbon, cost or environmental coefficient is applied because none is sourced.

## Weekly trend

Calendar weeks starting Monday (UTC), oldest first. Weeks with no activity are returned as real zeros so gaps stay visible. Collected weight is summed from `collected` events recorded by collectors.

## Not implemented

Per-material breakdowns, exports (CSV/PDF), saved reports and scheduled delivery.
