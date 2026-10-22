# Notifications (`notifications`)

In-app notifications per user. Email delivery goes through `integrations/email`.

**Status:** implemented (per-user list/read API; `notify()` for other modules). See `docs/api/notifications-api.md`.

## Ownership
- **Tables owned:** `notifications`
- **Files:** `constants.py`, `models.py`, `repository.py`, `router.py`, `schemas.py`, `service.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/notifications`, registered in `app/api/v1/router.py`.

## Notes
-

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API tests: `test_notifications.py` in `backend/tests/api/`; authorization of every route is checked by `backend/tests/security/test_route_inventory.py`.
Run: `make test-backend`.
