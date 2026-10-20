# Audit log (`audit`)

Append-only record of who did what, when. Other modules write entries through this module's service.

**Status:** `service.record` writes entries; `repository.list_page` reads them (served by `/api/v1/admin/audit-logs`).

## Ownership
- **Tables owned:** `audit_logs`
- **Files present:** `models.py`, `service.py`, `repository.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/audit/logs` (read-only, administrators), registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Never store secrets or password hashes in `changes`.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
