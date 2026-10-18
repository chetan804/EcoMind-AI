# Rewards and impact ledger (`rewards`)

Append-only ledger of points and verified impact per user.

**Status:** database models and migration exist; no router, service or repository yet (not implemented).

## Ownership
- **Tables owned:** `reward_ledger_entries`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/rewards/ledger`, `/api/v1/rewards/balance`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Other modules award points by calling this module's service inside their own transaction; there is no message broker.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
