# Authentication (`auth`)

Login, token refresh/rotation, logout and the current-user endpoint. Owns the server-side refresh sessions.

**Status:** database models and migration exist; no router, service or repository yet (not implemented).

## Ownership
- **Tables owned:** `auth_sessions`
- **Files present:** `models.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/auth/login`, `/refresh`, `/logout`, `/me`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Strategy: short-lived signed access token + rotating opaque refresh token in an HttpOnly cookie (docs/security/security-baseline.md).

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
