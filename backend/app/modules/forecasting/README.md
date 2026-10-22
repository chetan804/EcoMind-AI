# Waste forecasting (`forecasting`)

Stores and serves waste-generation forecasts produced by `ml/time_series` (algorithms loaded by name, see `engine.py`).

**Status:** implemented (router, schemas, repository, service, tests). See `docs/api/forecasting-api.md`.

## Ownership
- **Tables owned:** `forecast_results`, `reference_series`, `reference_series_points` (public reference data imported by `import-reference-series`, always labelled as such)
- **Files present:** the full module contract (`models`, `constants`, `schemas`, `repository`, `service`, `router`, `engine`, `series`, `importer`).

## Relationships
- **Depends on (via services / foreign keys):** `facilities`, `sorting_guide`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/forecasting`, registered in `app/api/v1/router.py`; documented in `docs/api/forecasting-api.md`.

## Notes
Reads historical observations through the collection/analytics service interfaces, never from their tables.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API tests: `test_forecasting.py` in `backend/tests/api/`; authorization of every route is checked by `backend/tests/security/test_route_inventory.py`.
Run: `make test-backend`.
