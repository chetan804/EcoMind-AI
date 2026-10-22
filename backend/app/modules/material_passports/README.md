# Material passports (`material_passports`)

Material passports and the append-only chain of custody.

**Status:** implemented (passports and custody API + tests; append-only trigger (migration 0007)). See `docs/api/material-passports-api.md`.

## Ownership
- **Tables owned:** `material_passports`, `custody_events`
- **Files:** `constants.py`, `models.py`, `repository.py`, `router.py`, `schemas.py`, `service.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users`, `facilities`, `sorting_guide`, `collection`, `circular_economy`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/material-passports`, registered in `app/api/v1/router.py`.

## Notes
Custody events are never updated or deleted; `sequence` orders them.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API tests: `test_material_passports.py` in `backend/tests/api/`; authorization of every route is checked by `backend/tests/security/test_route_inventory.py`.
Run: `make test-backend`.
