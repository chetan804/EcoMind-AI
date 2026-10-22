# API conventions

## Base paths
- Application API: **`/api/v1/...`**, REST + JSON, versioned. A breaking change creates `/api/v2`; `v1` keeps working until retired.
- Operational endpoints at the root (not versioned, not authenticated): `GET /health`, `GET /ready` (below).
- OpenAPI: `/api/v1/openapi.json` and `/api/v1/docs`, **disabled when `ENVIRONMENT=production`**.
- Routers are registered only in `backend/app/api/v1/router.py`.

## Operational endpoints (implemented)
| Endpoint | Meaning | Success | Failure |
|---|---|---|---|
| `GET /health` | Liveness: process is serving. Checks nothing external. | `200 {"status":"ok"}` | — |
| `GET /ready` | Readiness: PostgreSQL answers `SELECT 1` **and** `alembic_version` equals the head revision in this build. | `200 {"status":"ready","checks":{"database":{"status":"ok"},"migrations":{"status":"ok"}}}` | `503 {"status":"not_ready","checks":{...}}` with `detail` for failed checks (e.g. `schema revision is none, expected 0001; run alembic upgrade head`). Credentials never appear. |

## Conventions for every endpoint
- **Resources** are plural kebab-case nouns: `/waste-reports`, `/collection/tasks`. Actions that are not CRUD are sub-resources or verbs on a resource: `POST /collection/tasks/{id}/status`, `POST /routes/optimize`.
- **IDs** are UUIDs. **Timestamps** are ISO-8601 UTC with offset. **Quantities** carry the unit in the field name (`weight_kg`) or a `unit` field.
- **Methods/status:** `GET 200`; `POST` create `201` + `Location`; `PUT/PATCH 200`; `DELETE 204`; async-accepted `202`. `400` malformed request, `401` unauthenticated, `403` forbidden, `404` not found (also used to avoid revealing existence of forbidden resources), `409` conflict/invalid state transition, `413` payload too large, `422` validation failure, `429` rate limited, `500` unexpected, `503` dependency unavailable.
- **Validation:** Pydantic request schemas (`schemas.py`); unknown fields are rejected on write schemas.
- **Pagination:** `?page=1&page_size=25` (max 100). Response: `{"items":[...],"total":N,"page":1,"page_size":25}` (`common/pagination.py`). Filtering via explicit query parameters (`?status=verified&from=2026-01-01`); sorting via `?sort=created_at&order=desc` with an allow-list per endpoint.
- **Errors:** every non-2xx response uses one envelope (schema `ErrorResponse`):
  ```json
  {"error": {"code": "validation_error", "message": "Request validation failed",
             "details": [{"location": ["body","weight_kg"], "message": "...", "type": "..."}],
             "request_id": "9f3c..."}}
  ```
  Codes: `bad_request`, `unauthenticated`, `forbidden`, `not_found`, `method_not_allowed`, `conflict`, `payload_too_large`, `validation_error`, `rate_limited`, `internal_error`. Messages are safe to show to users; stack traces, SQL and configuration never appear.
- **Correlation:** clients may send `X-Request-ID` (8-64 chars `[A-Za-z0-9._-]`); the server echoes or generates one on every response and in error bodies and logs.
- **Authentication:** `Authorization: Bearer <access token>`; refresh via the HttpOnly cookie scoped to `/api/v1/auth` (see `docs/security/security-baseline.md`).
- **CORS:** only origins in `CORS_ALLOWED_ORIGINS`; credentials allowed; exposed header `X-Request-ID`.
- **Idempotency:** creates that may be retried by clients (uploads, awards) define a natural uniqueness rule in the database (for example one `earned` ledger entry per user+source).

## API surface
The API is implemented: 168 operations under `/api/v1` plus `/health` and `/ready`. The authoritative lists are generated from the code and checked in CI, so they cannot drift:

* every route with its HTTP method, required permission and roles: [route-permission-matrix.md](../security/route-permission-matrix.md);
* the OpenAPI document served at `/api/v1/docs` and `/api/v1/openapi.json` (disabled when `ENVIRONMENT=production`), with 234 schemas;
* per-area guides in `docs/api/` (for example `route-planning-api.md`, `tracking-api.md`, `marketplace-api.md`) and each module's `README.md`.

Endpoints are added with tests, a permission, an audit record where state changes, and an update of the generated documents in the same pull request (`scripts/security/generate_route_matrix.py --check`).

## Contract tests
`tests/contract/test_api_contract.py` enforces: all application routes under `/api/v1`, documented operational endpoints, published error schema, unique operation IDs, and agreement between the backend readiness schema and the frontend's Zod schema.
