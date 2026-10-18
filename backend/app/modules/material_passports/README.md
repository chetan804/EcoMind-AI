# Material passports (`material_passports`)

Material passports and the append-only chain of custody.

**Status:** database models and migration exist; no router, service or repository yet (not implemented).

## Ownership
- **Tables owned:** `material_passports`, `custody_events`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`, `facilities`, `sorting_guide`, `collection`, `circular_economy`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/material-passports`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Custody events are never updated or deleted; `sequence` orders them.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
