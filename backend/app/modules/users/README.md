# Users and roles (`users`)

User accounts, roles and the permission catalogue. Source of truth for who a person is and what they may do.

**Status:** implemented. Roles, permissions and grants are seeded by migrations (`0002` and later) and read from the database on every request (`rbac.py`, `repository.py`). Account management endpoints are served by the `administration` module under `/api/v1/admin/users` (list, view, activate, deactivate, change roles, reset two-step verification).

## Ownership
- **Tables owned:** `users`, `roles`, `permissions`, `user_roles`, `role_permissions`
- **Files:** `models.py`, `rbac.py`, `repository.py`. There is no router here by design: HTTP access is in `administration` and `auth`.

## Relationships
- **Depends on (via services / foreign keys):** no other module
- Other modules must use this module's `repository.py` lookups; never write to its tables directly.

## Roles
`citizen` (default for self-registration), `collector`, `facility_operator`, `manager`, `administrator`. The catalogue (48 permissions, 5 roles) is in `rbac.py`; `tests/integration/test_rbac_seed.py` compares it with the seeded database. A new permission needs a new migration with literal inserts (`0002` is frozen). First administrator: `python -m app.cli create-admin --email … --name …` (password from `ECOMIND_ADMIN_PASSWORD` or an interactive prompt, never an argument).

## Tests
`tests/api/test_administration.py`, `tests/integration/test_rbac_seed.py`, `tests/security/test_route_inventory.py` (deny by default).
Run: `make test-backend`.
