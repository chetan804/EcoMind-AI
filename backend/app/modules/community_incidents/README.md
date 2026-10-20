# Community incidents (`community_incidents`)

Incidents reported by the community (illegal dumping, overflowing bins, ...) and their resolution.

**Status:** implemented (report, list, summary, assign, lifecycle, notifications, audit). See docs/api/community-incidents-api.md.

## Ownership
- **Tables owned:** `community_incidents`
- **Files present:** `models.py`, `constants.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users`, `waste_reports` (photo uploads), `notifications`, `audit`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/community-incidents`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
-

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API behaviour: `backend/tests/api/test_community_incidents.py` (permissions, privacy, photo ownership, lifecycle, notifications, audit).
Run: `make test-backend`.
