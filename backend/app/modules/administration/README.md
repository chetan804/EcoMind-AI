# Administration (`administration`)

Cross-cutting administrative operations (for example system configuration views). Owns no tables.

**Status:** boundary defined only; nothing implemented.

## Ownership
- **Tables owned:** none
- **Files present:** none yet. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`, `audit`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/admin/*`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Orchestrates through other modules' services; adds no business rules of its own.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
