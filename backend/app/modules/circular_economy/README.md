# Circular economy (`circular_economy`)

Material recovery records and their verification. Only verified records count towards recovery metrics.

**Status:** implemented (recovery records API + tests). See `docs/api/circular-economy-api.md`.

## Ownership
- **Tables owned:** `recovery_records`
- **Files:** `constants.py`, `models.py`, `repository.py`, `router.py`, `schemas.py`, `service.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users`, `facilities`, `sorting_guide`, `waste_reports`, `collection`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/circular-economy`, registered in `app/api/v1/router.py`.

## Notes
-

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API tests: `test_recovery_records.py` in `backend/tests/api/`; authorization of every route is checked by `backend/tests/security/test_route_inventory.py`.
Run: `make test-backend`.
