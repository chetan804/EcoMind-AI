# Audit log (`audit`)

Append-only record of who did what, when. Other modules write entries through this module's service.

**Status:** implemented. `service.record` writes entries; `repository.list_page` reads them (served read-only to administrators by `/api/v1/admin/audit-logs`). Authentication lockouts are derived from these rows (`occurred_at`).

## Ownership
- **Tables owned:** `audit_logs`
- **Files:** `models.py`, `service.py`, `repository.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users` (`actor_id`, `ON DELETE SET NULL`)
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
No router of its own: `GET /api/v1/admin/audit-logs` (permission `audit:read`) lives in the `administration` module. See [docs/api/administration-api.md](../../../../docs/api/administration-api.md).

## Notes
- Never store secrets or password hashes in `changes`.
- Append-only is enforced by a database trigger from migration `0017`: updates and deletes are refused, except the automatic `actor_id` → NULL when a user row is deleted. TRUNCATE is not covered.

## Tests
`tests/integration/test_append_only_records.py`, `tests/api/test_administration.py`, and the audit assertions in most API tests.
Run: `make test-backend`.
