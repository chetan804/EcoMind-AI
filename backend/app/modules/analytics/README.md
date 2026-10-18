# Dashboard analytics (`analytics`)

Read-only aggregates and trends for dashboards and reports. Owns no tables.

**Status:** boundary defined only; nothing implemented.

## Ownership
- **Tables owned:** none
- **Files present:** none yet. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `collection`, `waste_reports`, `circular_economy`, `facilities`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/analytics/*`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Must obtain data through other modules' service/read interfaces, not ad hoc SQL against their tables.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
