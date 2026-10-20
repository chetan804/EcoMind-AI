# Dashboard analytics (`analytics`)

Read-only aggregates and trends for dashboards and reports. Owns no tables.

**Status:** implemented: `/api/v1/analytics/overview` and `/weekly-trend` (docs/api/analytics-api.md).

## Ownership
- **Tables owned:** none
- **Files present:** `router.py`, `schemas.py`, `service.py`. It has no repository: queries are aggregates over other modules' tables, read-only (it never writes).

## Relationships
- **Depends on (via services / foreign keys):** `collection`, `waste_reports`, `circular_economy`, `facilities`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/analytics/*`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Rule 6 of docs/architecture/component-boundaries.md asks read aggregation to go through other modules' read interfaces. Where a module already publishes an aggregate (`circular_economy.summary`, `rewards.summary`, `community_incidents.summary`) analytics calls it. For simple counts and sums over tables with no such interface (reports, tasks, collection events, vehicles, facilities, anomaly alerts, passports) analytics runs read-only `SELECT` aggregates on the owning module's model classes; it never writes. This is a documented, deliberate deviation: wrapping each count in a one-line function per module would add eight pass-throughs without protecting any invariant. If a module's table changes, `backend/tests/api/test_analytics.py` fails.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API behaviour: `backend/tests/api/test_analytics.py`.
Run: `make test-backend`.
