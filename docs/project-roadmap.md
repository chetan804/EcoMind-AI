# Project roadmap and acceptance criteria

Modules are implemented in dependency order (`docs/architecture/component-boundaries.md`). Each milestone ends with working, tested, documented behaviour; a feature is "done" only per the acceptance rule in `docs/requirements/functional-requirements.md`.

## M0 — Foundation (this repository state) ✔
**Delivered:** canonical structure; locked stack; documentation set; configuration and environment templates; backend app factory, config validation, error envelope, request ids, security primitives, `/health` and `/ready`; initial schema (29 tables) with Alembic migration tested on PostgreSQL; frontend shell with real system-status page; ML preprocessing utility; Dockerfiles and Compose; Makefile; GitHub Actions; test infrastructure at every layer.
**Not delivered (by design):** any business feature, trained model, dataset, seed data.

## M1 — Identity and access (first feature milestone)
Scope: `users`, `auth`, `audit` (write path), role/permission seed, frontend `auth` + guards, `users` admin screens.
Acceptance: login/refresh/logout/me work with rotation and reuse detection; permission checks enforced and tested (401/403 matrix); first administrator created by a documented, non-default-credential command; audit entries for sign-in and role changes; Playwright sign-in workflow; no tokens in `localStorage`.

## M2 — Reference data and reports
Scope: `sorting_guide` (categories, guidance CRUD + public read), `facilities`, `fleet`, `waste_reports` + media upload (`integrations/file_storage`), frontend report create/list/detail and sorting guide.
Acceptance: upload validation (type, size, pixels) tested; reports filterable and paginated; files persist across restarts; media hash stored.

## M3 — Collection operations
Scope: `collection` (tasks, assignments, status machine, events), collector "my tasks" screen, `notifications` basics.
Acceptance: invalid transitions rejected (409); every transition writes history in the same transaction; one active assignment enforced; end-to-end workflow report → task → assigned → collected.

## M4 — Classification
Precondition: dataset manifest with licence, label mapping, split, evaluation per `docs/ml/evaluation-protocol.md`.
Scope: baseline model trained and evaluated (evidence in a model card), `classification` module, review queue, classification UI showing object, material category, confidence and guidance.
Acceptance: no prediction is returned without an active, carded model version; reported metrics reproduce from `ml/configs` + manifest; low-confidence cases routed to review; hash-verified artifact loading.

## M5 — Routing, circular economy, passports, rewards
Scope: `route_planning` (+ mapping adapter ADR), `circular_economy` with verification, `material_passports`, `rewards`.
Acceptance: only verified recovery counts; custody append-only; ledger idempotent and balance equals sum of entries.

## M6 — Analytics, forecasting, anomalies, incidents
Scope: `analytics` + dashboard, `forecasting` with baseline and chronological evaluation, `anomaly_detection` with documented thresholds and explanations, `community_incidents`.
Acceptance: dashboards computed from real records only; forecast beats or is reported against baseline; anomaly validation on known/labelled-simulated cases; simulated data labelled.

## M7 — Hardening and release
Security review against `docs/security/security-baseline.md` (CSP, rate limiting, dependency audit, backup/restore drill), performance check against NFR-PERF-1, accessibility audit, deployment to a chosen platform with documented runbook.

## Backlog / follow-ups noted during the foundation
- Backend dependency lock/constraints file; automated dependency and vulnerability scanning.
- Content-Security-Policy and rate limiting.
- Select UI approach (ADR) when the second screen is built.
- Sensor integration only after a requirement and hardware exist.

## Recommended first feature milestone
**M1 — Identity and access.** Everything else depends on `users`/`auth`/permissions, and it exercises the whole vertical slice (schema → service → router → API tests → frontend → e2e) that the foundation prepared.
