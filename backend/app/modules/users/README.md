# Users and roles (`users`)

User accounts, roles and the permission catalogue. Source of truth for who a person is and what they may do.

**Status:** database models and migration exist; no router, service or repository yet (not implemented).

## Ownership
- **Tables owned:** `users`, `roles`, `permissions`, `user_roles`, `role_permissions`
- **Files present:** `models.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** no other module
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/users`, `/api/v1/roles` (administration), registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Passwords are stored only as Argon2id hashes (`core/security.py`). Roles are plain data; the seed set is defined in the first auth milestone.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
