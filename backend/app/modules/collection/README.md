# Collection operations (`collection`)

Collection tasks, assignments, status history and field events.

**Status:** implemented (router, schemas, repository, service; tasks are created from verified reports or by hand, assigned, started, completed with a weight, failed, cancelled or rescheduled). API: [docs/api/collections-api.md](../../../../docs/api/collections-api.md).

## Ownership
- **Tables owned:** `collection_tasks`, `collection_assignments`, `collection_task_status_history`, `collection_events`
- **Files:** `models.py`, `constants.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users`, `facilities`, `fleet`, `waste_reports`; completion earns reward points through `rewards`, notifies the reporter through `notifications` and writes audit entries.
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/collection/tasks` (list, create, view) and `/tasks/{id}/assign|start|events|complete|fail|cancel|reschedule`, registered in `app/api/v1/router.py`. Permissions: `collection:read`, `collection:manage`, `collection:execute` (see the generated [route matrix](../../../../docs/security/route-permission-matrix.md)). A collector can act only on tasks assigned to them.

## Notes
- Every status change writes a history row in the same transaction. The history is append-only in the database from migration `0017` (updates and deletes are refused).
- Allowed transitions are in `constants.py`; one active assignment per task is a partial unique index.

## Tests
`tests/api/test_collection.py`; database rules in `tests/integration/test_schema_constraints.py` and `test_append_only_records.py`; the browser journey in `tests/e2e/specs/core-workflow.spec.ts`.
Run: `make test-backend`.
