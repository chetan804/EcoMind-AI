# Route planning (`route_planning`)

Route plans and ordered stops for a vehicle/driver, including optimizer output.

**Status:** implemented (optimizer, schemas, repository, service, router, tests). See `docs/api/route-planning-api.md`.

## Ownership
- **Tables owned:** `route_plans`, `route_stops`
- **Files present:** the full module contract plus `optimizer.py` (pure computation).

## Relationships
- **Depends on (via services / foreign keys):** `users`, `facilities`, `fleet`, `collection`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/route-planning`, registered in `app/api/v1/router.py`; documented in `docs/api/route-planning-api.md`.

## Notes
Stop **order** comes from the platform's own optimiser (straight-line distances, no ETA). `GET /plans/{id}/road-route` asks the routing provider (Google Routes API, `integrations/mapping`) for road geometry, distance and duration for that order; it is never stored, answers `available: false` with a reason when there is no server key or the call fails, and the screen then labels straight lines as such.
A stop targets exactly one of a collection task or a facility (database CHECK).

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
