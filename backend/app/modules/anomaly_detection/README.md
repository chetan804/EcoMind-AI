# Anomaly detection (`anomaly_detection`)

Stores, explains and triages operational anomaly alerts produced by `ml/time_series` (algorithms loaded by name, see `forecasting/engine.py`).

**Status:** implemented (router, schemas, repository, service, tests). See `docs/api/anomalies-api.md`.

## Ownership
- **Tables owned:** `anomaly_alerts`
- **Files present:** the full module contract (`models`, `constants`, `schemas`, `repository`, `service`, `router`).

## Relationships
- **Depends on (via services / foreign keys):** `users`, `facilities`, `sorting_guide`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/anomalies`, registered in `app/api/v1/router.py`; documented in `docs/api/anomalies-api.md`.

## Notes
Every alert must carry a human-readable explanation (database CHECK).

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API tests: `test_anomalies.py` in `backend/tests/api/`; authorization of every route is checked by `backend/tests/security/test_route_inventory.py`.
Run: `make test-backend`.
