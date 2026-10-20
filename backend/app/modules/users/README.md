# Users and roles (`users`)

User accounts, roles and the permission catalogue. Source of truth for who a person is and what they may do.

**Status:** roles, permissions and grants are seeded and used for authorization (`rbac.py`, migration `0002`); `repository.py` provides lookups. **No user-management endpoints yet** (list, deactivate, change roles): not implemented.

## Ownership
- **Tables owned:** `users`, `roles`, `permissions`, `user_roles`, `role_permissions`
- **Files present:** `models.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** no other module
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## Roles
`citizen` (default for self-registration), `collector`, `facility_operator`, `manager`, `administrator`. The catalog (38 permissions, 5 roles) is in `rbac.py`; a test compares it with the seeded database. First administrator: `python -m app.cli create-admin --email … --name …` (password from `ECOMIND_ADMIN_PASSWORD` or an interactive prompt, never an argument).

## API (planned, not implemented)
`/api/v1/users` (list, view, deactivate, assign roles), requiring `users:read` / `users:manage`.
