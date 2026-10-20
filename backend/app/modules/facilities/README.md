# Facilities (`facilities`)

Processing centers, depots, transfer stations and drop-off points.

**Status:** implemented and verified (API + database); used by the Facilities and Locations screens.

## Ownership
- **Tables owned:** `facilities`, `zones`
- **Files:** `models.py`, `constants.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `zone_router.py` (zones, mounted at `/api/v1/zones`).

## Relationships
- **Depends on:** no other module (uses `audit` and the `auth` principal)
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/facilities` (see [docs/api/facilities-api.md](../../../../docs/api/facilities-api.md)). Registered in `app/api/v1/router.py`.

## Notes
- Zones are named service areas with no geometry; a facility may belong to one active zone. Zones are retired with `is_active=false`.
- Facilities are retired with `status=inactive`, never deleted.
- `contact_email` is only returned to callers with `facilities:manage`.

## Tests
`tests/api/test_facilities.py` (32 tests) and `tests/api/test_zones.py` (13 tests). Constraints: `tests/integration/test_schema_constraints.py`.
Run: `make test-backend`.
