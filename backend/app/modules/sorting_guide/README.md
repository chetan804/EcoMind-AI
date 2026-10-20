# Material sorting guide (`sorting_guide`)

Waste-material categories and the disposal/sorting guidance for each. Defines the vocabulary of materials used everywhere else.

**Status:** implemented (API + tests). See `docs/api/sorting-guide-api.md`. Categories are seeded by migrations 0004 and 0006; no guidance content is shipped.

## Ownership
- **Tables owned:** `material_categories`, `sorting_guidance`
- **Files present:** `models.py`, `constants.py`. Add `router.py`, `schemas.py`, `repository.py`, `service.py` and the other files of the module contract only when they are needed (docs/architecture/component-boundaries.md).

## Relationships
- **Depends on (via services / foreign keys):** no other module
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/sorting-guide`, registered in `app/api/v1/router.py`.

## Notes
A material category is what something is made of; it is not the identified object (see classification).

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. When endpoints are added, add API tests in `backend/tests/api/` and authorization tests in `backend/tests/security/`.
Run: `make test-backend`.
