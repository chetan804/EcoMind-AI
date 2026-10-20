# Rewards and impact ledger (`rewards`)

Append-only ledger of points and verified impact per user.

**Status:** implemented (ledger read model, adjustments/reversals, earning on collection completion). See `docs/api/rewards-api.md`.

## Ownership
- **Tables owned:** `reward_ledger_entries`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/rewards`, registered in `app/api/v1/router.py`.

## Notes
Other modules award points by calling this module's service inside their own transaction; there is no message broker.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
