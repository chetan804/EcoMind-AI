# Notifications (`notifications`)

In-app notifications per user. Email delivery goes through `integrations/email`.

**Status:** implemented (per-user list/read API; `notify()` for other modules). See `docs/api/notifications-api.md`.

## Ownership
- **Tables owned:** `notifications`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/notifications`, registered in `app/api/v1/router.py`.

## Notes
-

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
