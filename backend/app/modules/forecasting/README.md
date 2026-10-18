# Waste forecasting (`forecasting`)

Stores and serves waste-generation forecasts produced by `ml/forecasting`.

**Status:** database models and migration exist; no router, service or repository yet (not implemented).

## Ownership
- **Tables owned:** `forecast_results`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `facilities`, `sorting_guide`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/forecasts`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Reads historical observations through the collection/analytics service interfaces, never from their tables.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
