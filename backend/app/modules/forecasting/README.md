# Waste forecasting (`forecasting`)

Stores and serves waste-generation forecasts produced by `ml/time_series` (algorithms loaded by name, see `engine.py`).

**Status:** implemented (router, schemas, repository, service, tests). See `docs/api/forecasting-api.md`.

## Ownership
- **Tables owned:** `forecast_results`
- **Files present:** the full module contract (`models`, `constants`, `schemas`, `repository`, `service`, `router`, `engine`, `series`, `importer`).

## Relationships
- **Depends on (via services / foreign keys):** `facilities`, `sorting_guide`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/forecasting`, registered in `app/api/v1/router.py`; documented in `docs/api/forecasting-api.md`.

## Notes
Reads historical observations through the collection/analytics service interfaces, never from their tables.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
