# Rewards and impact ledger (`rewards`)

Append-only ledger of points and verified impact per user.

**Status:** implemented (ledger read model, adjustments/reversals, earning on collection completion). See `docs/api/rewards-api.md`.

## Ownership
- **Tables owned:** `reward_ledger_entries`, `reward_items` (staff-entered catalogue), `reward_redemptions`
- **Files:** `adjustments.py`, `catalog.py`, `constants.py`, `models.py`, `router.py`, `schemas.py`, `service.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/rewards`, registered in `app/api/v1/router.py`.

## Notes
Other modules award points by calling this module's service inside their own transaction; there is no message broker.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API tests: `test_rewards.py`, `test_rewards_catalogue.py` in `backend/tests/api/`; authorization of every route is checked by `backend/tests/security/test_route_inventory.py`.
Run: `make test-backend`.
