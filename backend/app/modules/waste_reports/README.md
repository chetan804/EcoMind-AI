# Waste reports and media (`waste_reports`)

Reports of waste submitted by users, and the metadata of uploaded images (bytes live in the file-storage integration).

**Status:** implemented and used by the web app's Reports screen (API, database, browser journeys). Reports can be listed by status, reporter, date range and a bounding box (`min_latitude`, `max_latitude`, `min_longitude`, `max_longitude`; zones have no geometry, so "area" means a box).

## Ownership
- **Tables owned:** `waste_reports`, `media_assets`
- **Files:** `models.py`, `constants.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `images.py`, `errors.py`.

## Relationships
- **Depends on:** `users`, `audit`, `auth` (principal), `integrations/file_storage`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/waste-reports` (see [docs/api/waste-reports-api.md](../../../../docs/api/waste-reports-api.md)). Registered in `app/api/v1/router.py`.

## Notes
- `images.py` is the only place that decodes uploads: format from the bytes, size guards, re-encode to strip metadata.
- `service.py` decides visibility (404 rather than 403 for other people's data) and owns every transaction; `repository.py` has no commits.
- Review transitions live in `constants.ALLOWED_TRANSITIONS`.
- Upload -> classify -> submit: a media asset exists before it is attached to a report. Classification is a separate module (`classification`); a prediction is stored against the media asset and needs an activated model, otherwise the API answers `503 no_active_model`.

## Tests
`tests/unit/test_images.py`, `tests/unit/test_file_storage.py`, `tests/unit/test_search_pattern.py`, `tests/api/test_waste_reports.py`, `tests/api/test_waste_report_media.py` (90 tests; includes two-thread races for idempotency, review and photo claiming). Constraints: `tests/integration/test_schema_constraints.py`, `test_migrations.py`.
Run: `make test-backend`.
