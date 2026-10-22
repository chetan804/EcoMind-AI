# Material sorting guide (`sorting_guide`)

Waste-material categories and the disposal/sorting guidance for each. Defines the vocabulary of materials used everywhere else.

**Status:** implemented (API + tests). See `docs/api/sorting-guide-api.md`. Categories are seeded by migrations 0004 and 0006; no guidance content is shipped.

## Ownership
- **Tables owned:** `material_categories`, `sorting_guidance`
- **Files:** `constants.py`, `models.py`, `repository.py`, `router.py`, `schemas.py`, `service.py`.

## Relationships
- **Depends on (via services / foreign keys):** no other module
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/sorting-guide`, registered in `app/api/v1/router.py`.

## Notes
A material category is what something is made of; it is not the identified object (see classification).

## Tests
The migration, naming rules and selected database constraints are covered by `backend/tests/integration/test_migrations.py` and `test_schema_constraints.py`. API tests: `test_sorting_guide.py` in `backend/tests/api/`; authorization of every route is checked by `backend/tests/security/test_route_inventory.py`.
Run: `make test-backend`.
