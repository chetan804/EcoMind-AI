# Fleet (`fleet`)

Fleet vehicles, capacity and availability.

**Status:** implemented (router, schemas, service, repository). See `docs/api/fleet-api.md`. Vehicle positions live in the separate `tracking` module; a vehicle has no coordinates of its own.

## Ownership
- **Tables owned:** `fleet_vehicles`
- **Files present:** `models.py`, `constants.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.

## Relationships
- **Depends on (via services / foreign keys):** `facilities`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/fleet/vehicles`, registered in `app/api/v1/router.py`; documented in `docs/api/fleet-api.md`.

## Notes
Driver assignment is recorded on collection assignments and route plans, not on the vehicle.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API tests are in `backend/tests/api/`.
Run: `make test-backend`.
