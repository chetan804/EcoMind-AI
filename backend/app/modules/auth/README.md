# Authentication (`auth`)

Login, token refresh/rotation, logout and the current-user endpoint. Owns the server-side refresh sessions.

**Status:** implemented and tested (register, login, refresh rotation with reuse detection, logout, change password, current user, request-auth dependencies).

## Ownership
- **Tables owned:** `auth_sessions`, `account_tokens`, `mfa_factors`, `mfa_recovery_codes`
- **Files:** `dependencies.py`, `errors.py`, `mfa.py`, `models.py`, `policy.py`, `recovery.py`, `repository.py`, `router.py`, `schemas.py`, `service.py`, `totp.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
All under `/api/v1/auth` (see `docs/api/auth-api.md`): `POST /register`, `POST /login`, `POST /refresh`, `POST /logout`, `POST /change-password`, `GET /me`.

## Files
`router.py` (HTTP + cookie handling), `service.py` (use cases and transactions), `repository.py`, `schemas.py`, `policy.py` (password rules and limits), `errors.py`, `dependencies.py` (`get_current_principal`, `require_permissions`, CSRF header guard).

## Protecting an endpoint in another module
```python
from app.modules.auth.dependencies import Principal, require_permissions


@router.get("/things")
def list_things(principal: Annotated[Principal, Depends(require_permissions("things:read"))]): ...
```
Add the permission string to `users/rbac.py` and a *new* migration that grants it; never edit an applied migration.

## Security notes
See `docs/security/security-baseline.md` for the full model, limits and known gaps.

## Tests
`backend/tests/api/test_auth_flow.py`, `test_auth_sessions.py`, `test_auth_limits.py`, `backend/tests/security/test_authorization.py`, `backend/tests/unit/test_password_policy.py`. Run: `make test-backend`.
