# Data flow

Flows marked *implemented* exist in the repository; the rest are the **target** flows modules must follow when built.

## Implemented: status check
1. Browser loads the SPA; `SystemStatusPage` calls `GET /health` and `GET /ready` through the shared API client (`VITE_API_BASE_URL` or the dev/preview proxy).
2. `/health` answers without touching dependencies. `/ready` opens a PostgreSQL connection, runs `SELECT 1`, and compares `alembic_version` with the head revision shipped in the image; any failure yields `503` with a structured report and no credentials.

## Request lifecycle (all `/api/v1` endpoints)
`RequestContextMiddleware` assigns/echoes `X-Request-ID` → CORS → router → dependencies (database session, current user, permission check) → service (business rules, one transaction, commit) → repository (queries) → Pydantic response schema. Failures become the structured error envelope (`docs/api/api-conventions.md`); unexpected exceptions are logged with the request id and returned as a generic 500.

## Target: report → classify → collect → recover
1. User uploads an image: `waste_reports` validates it (`ml/common/preprocessing`), stores bytes via `integrations/file_storage`, records a `media_assets` row.
2. `classification` runs the active model version's inference code, stores a `classification_predictions` row (identified object, material category, confidences). Low confidence → "needs review". Guidance is looked up from `sorting_guide` by category.
3. User submits a `waste_reports` row referencing the media; staff may confirm/correct the prediction (review fields).
4. `collection` creates a task (status history written with each transition), assigns a collector/vehicle; `route_planning` orders stops.
5. The collector records `collection_events` (arrival, collected weight in kg, delivery).
6. A facility records a `recovery_records` row; a verifier marks it verified. Only verified records count in metrics. `material_passports` appends custody events; `rewards` appends ledger entries (idempotent per source) — each via the owning module's service in the caller's transaction.
7. `audit` records sensitive actions; `notifications` informs affected users.

## Target: ML loop
Datasets (manifest in `datasets/manifests/`) → `ml/<capability>/training` (config from `ml/configs`) → evaluation report + model card (`docs/ml/model-cards`) → artifact + registry manifest (`ml/model_registry`) → backend loads artifacts from `MODEL_ARTIFACTS_DIR` after hash verification → predictions stored with the model version → human review corrections feed the next dataset version.
