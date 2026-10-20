# Facilities (`facilities`)

Processing centers, depots, transfer stations and drop-off points.

**Status:** implemented and verified locally (API + database); not yet wired into the web UI.

## Ownership
- **Tables owned:** `facilities`
- **Files:** `models.py`, `constants.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.

## Relationships
- **Depends on:** no other module (uses `audit` and the `auth` principal)
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/facilities` (see [docs/api/facilities-api.md](../../../../docs/api/facilities-api.md)). Registered in `app/api/v1/router.py`.

## Notes
- Facilities are retired with `status=inactive`, never deleted.
- `contact_email` is only returned to callers with `facilities:manage`.

## Tests
`tests/api/test_facilities.py` (32 tests). Constraints: `tests/integration/test_schema_constraints.py`.
Run: `make test-backend`.
