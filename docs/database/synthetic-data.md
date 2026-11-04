# Synthetic demonstration data (Hyderabad)

> **Everything this generator produces is fictional.** It exists so that dashboards, analytics, tests
> and load checks have a realistic volume of data. It is never real citizen data, never official
> municipal data, and must never be loaded into a production database (the tool refuses).

Code: [`scripts/demo/synthetic/`](../../scripts/demo/synthetic/README.md). Tests:
`backend/tests/integration/test_synthetic_dataset.py`.

## Architecture

| Module | Role |
|---|---|
| `geography.py` | 31 localities (Uppal to Musheerabad): approximate centre, zone type, invented report weight |
| `profiles.py` | size profiles `test`, `development`, `integration`, `large`, `stress` |
| `ids.py` | deterministic ids (`53594e54-` prefix) and one independent random stream per entity |
| `world.py` | `World.build(seed, profile, anchor)`: users, zones, facilities, vehicles, reward items, marker text |
| `days.py` | `Simulator.day(date)`: all rows for one day across 17 tables, carrying running state |
| `loader.py` | psycopg `COPY` into a staging table, upsert, per-day resume, guards, 24 SQL checks, cleanup |
| `cli.py` | `plan`, `load`, `verify`, `report`, `cleanup` |
| `run_analytics.py` | calls the application's own forecast and anomaly endpoints |
| `compare_api.py` | reconciles the dashboard API with independent SQL |

Design choices:

* **Deterministic and idempotent.** Same seed, profile and anchor give identical rows and keys; loading
  twice adds nothing (`ON CONFLICT DO NOTHING`); loading a different seed/profile/anchor into the same
  database is refused.
* **Resumable.** The loader works one day at a time and skips a day whose first task already exists;
  the simulator still generates the day so running state (vehicle load, passport chains) is identical.
  Each batch is committed, so an interrupted run resumes without duplicates (tested).
* **Schema-compatible.** A test compares the generator's column lists with the live schema, so a
  migration that adds a required column fails the test instead of silently breaking the loader.
* **Business rules respected.** Recovered weight never exceeds input, resolved incidents have
  `resolved_at`, ledger reversals reference an earlier entry, cancelled redemptions are refunded,
  custody chains follow `material_passports.service.SUCCESSORS`, route stops reference exactly one of
  task or facility.
* **Failure paths are included:** rejected and contaminated reports, failed and cancelled tasks, skipped
  stops, pending and rejected recovery verification, cancelled redemptions, declined marketplace
  requests, dismissed incidents. Weekly volume has weekday/weekend seasonality, four spaced surge weeks and
  a dip week, so the real anomaly detector has something to find.

## Row counts

Measured with `python -m synthetic plan` / `load` (anchor 2026-11-04, seed 42):

| Table | test | development |
|---|---|---|
| waste_reports | | 2,184 |
| collection_tasks | | 2,056 |
| collection_assignments | | 1,958 |
| collection_task_status_history | | 8,048 |
| collection_events | | 5,287 |
| route_plans / route_stops | | 1,405 / 3,260 |
| vehicle_location_events | | 15,400 |
| recovery_records | | 947 |
| material_passports / custody_events | | 518 / 3,239 |
| reward_ledger_entries / reward_redemptions | | 2,195 / 666 |
| notifications | | 3,362 |
| community_incidents | | 226 |
| marketplace_listings / requests | | 27 / 29 |
| Dimensions: zones / facilities / vehicles / users / reward items | | 31 / 21 / 18 / 452 / 8 |
| **All synthetic rows** | ~9.7 k | **51,789** |

Planned totals for the other profiles: integration ~285 k, large ~1.81 M. The `stress` profile (5 M+)
is defined but **has not been planned or loaded**. Load speed with `COPY` was ~13-15 k rows/s on the
2-CPU sandbox (development in about 3 s). The large profile has **not been loaded**; only its plan
was computed (about 16 s).

## What is NOT generated, and why

| Domain | Reason |
|---|---|
| `audit_logs` | append-only audit trail; fabricating "who did what" would be a false record |
| `classification_predictions`, `classification_model_versions` | would be fabricated model output; no active approved classifier exists |
| `forecast_results`, `anomaly_alerts` | produced by running the real forecaster and detector (`run_analytics.py`) |
| `media_assets`, marketplace photos | would need real image files |
| `auth_sessions`, `account_tokens`, `mfa_*` | credentials and sessions are never fabricated; synthetic users cannot sign in |
| `support_tickets` and replies, assistant conversations | free text that would pose as real people's words |
| `role_requests` | approval workflow state belongs to real users |
| `knowledge_articles`, `sorting_guidance`, `material_categories`, permissions, roles | reference content seeded by migrations/CLI |

## Honesty labels and limitations

* Zones are named `[Demo] <locality>` with code `SYN-ZN-nn` and a description saying they are approximate
  and not official wards or circles. **Coordinates are approximate locality centres written from general
  knowledge, not surveyed points.** Addresses are descriptive text only.
* Per-locality report weights are **invented** to make a plausible spread; they are not census data.
* GPS pings are interpolated between stops with the source `simulator`; they are not road routes.
* Weights, timings and rates are drawn from invented distributions. Treat all dashboards fed from this
  data as a demonstration, not as findings about Hyderabad.
* Points: 10 per kg (the application's own rule), so net points are large with this volume.
* The `test` profile produced no redemptions; development produced 666.

## Validation

1. `verify` runs 24 SQL integrity checks (orphans, enum/timeline order, weight conservation, ledger
   balance, custody order, label prefix). All pass on the development profile.
2. `compare_api.py` reconciles `/analytics/overview` and `/analytics/weekly-trend` with independent SQL,
   using the window the API reports: **73 of 73 figures agreed** on the development load (including the
   12 weekly points, report/task status counts, collected kg, recovery, rewards, passports, fleet).
3. Pagination: lists are served server-side by the application as before; nothing here changes that.
4. Real analytics on the loaded history: 4-week forecasts saved for the platform series and the two
   reference series; the anomaly detector flagged one platform week (collected 32,801 kg vs 16,766 expected).
   The three other planned surges were not flagged by the detector's thresholds; no thresholds were
   changed to make it do so.

## Cleanup

```bash
python -m synthetic cleanup --profile development --yes-delete-synthetic
```

Deletes by id prefix in reverse dependency order (real demo accounts and reference series stay).
An earlier version of `cleanup` and the dimension upsert did not commit; a unit test that read through
the same connection hid it. Fixed: both commit, and the tests now read through a second connection.
