# Material passports (`material_passports`)

Material passports and the append-only chain of custody.

**Status:** implemented (passports and custody API + tests; append-only trigger (migration 0007)). See `docs/api/material-passports-api.md`.

## Ownership
- **Tables owned:** `material_passports`, `custody_events`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`, `facilities`, `sorting_guide`, `collection`, `circular_economy`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/material-passports`, registered in `app/api/v1/router.py`.

## Notes
Custody events are never updated or deleted; `sequence` orders them.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
