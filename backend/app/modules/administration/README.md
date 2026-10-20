# Administration (`administration`)

Cross-cutting administrative operations (for example system configuration views). Owns no tables.

**Status:** implemented (users, roles, audit log, system information). See docs/api/administration-api.md.

## Ownership
- **Tables owned:** none
- **Files present:** `router.py`, `schemas.py`, `service.py`. No repository: row access goes through `users`, `audit` and `auth` repositories.

## Relationships
- **Depends on (via services / foreign keys):** `users`, `audit`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/admin/*`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Orchestrates through the `users`, `audit` and `auth` repositories. Its own rules: a mandatory audited reason, no self-modification, and the last active administrator is protected.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API behaviour: `backend/tests/api/test_administration.py`.
Run: `make test-backend`.
