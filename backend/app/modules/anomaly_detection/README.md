# Anomaly detection (`anomaly_detection`)

Stores, explains and triages operational anomaly alerts produced by `ml/anomaly_detection`.

**Status:** database models and migration exist; no router, service or repository yet (not implemented).

## Ownership
- **Tables owned:** `anomaly_alerts`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`, `facilities`, `sorting_guide`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/anomaly-alerts`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Every alert must carry a human-readable explanation (database CHECK).

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
