# Waste classification (`classification`)

Runs inference through `ml/waste_classification`, stores predictions per model version, and records human review. Keeps the identified object, the material category and the confidence values separate.

**Status:** database models and migration exist; no router, service or repository yet (not implemented).

## Ownership
- **Tables owned:** `classification_model_versions`, `classification_predictions`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** `users`, `sorting_guide`, `waste_reports`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API (planned, not implemented)
`/api/v1/classification/predictions`, `/api/v1/classification/model-versions`, registered in `app/api/v1/router.py`. See docs/api/api-conventions.md.

## Notes
Only values produced by the deployed model are stored or shown. No model is trained yet, so this module must not return predictions until one is.

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
