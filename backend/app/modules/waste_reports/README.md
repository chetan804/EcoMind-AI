# Waste reports and media (`waste_reports`)

Reports of waste submitted by users, and the metadata of uploaded images (bytes live in the file-storage integration).

**Status:** database models and migration exist; no router, service or repository yet (not implemented).

## Ownership
- **Tables owned:** `waste_reports`, `media_assets`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/waste-reports`, `/api/v1/media`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Upload -> classify -> submit: a media asset exists before it is attached to a report.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
