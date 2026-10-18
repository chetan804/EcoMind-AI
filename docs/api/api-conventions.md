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

## Initial API contract (planned; implement incrementally)
Nothing below exists yet except `/health` and `/ready`; each module README lists its prefix. Endpoints are added with tests and this table is updated in the same pull request.

| Area | Planned endpoints (under `/api/v1`) | Module |
|---|---|---|
| Authentication | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` | auth |
| User administration | `GET/POST /users`, `GET/PATCH /users/{id}`, `GET /roles`, `PUT /users/{id}/roles` | users |
| Waste reports | `GET/POST /waste-reports`, `GET/PATCH/DELETE /waste-reports/{id}` (filters: status, reporter, date, area) | waste_reports |
| Upload & classification | `POST /media` (multipart), `POST /classification/predictions`, `PATCH /classification/predictions/{id}/review`, `GET /classification/model-versions` | waste_reports, classification |
| Collection | `GET/POST /collection/tasks`, `GET /collection/tasks/{id}`, `POST /collection/tasks/{id}/assignments`, `POST /collection/tasks/{id}/status`, `POST /collection/tasks/{id}/events` | collection |
| Routes | `POST /routes/optimize`, `GET/POST /routes`, `GET /routes/{id}` | route_planning |
| Facilities & fleet | `GET/POST /facilities`, `GET/PATCH /facilities/{id}`, `GET/POST /fleet/vehicles`, `GET/PATCH /fleet/vehicles/{id}` | facilities, fleet |
| Circular economy | `GET/POST /circular-economy/recovery-records`, `POST /circular-economy/recovery-records/{id}/verification` | circular_economy |
| Analytics | `GET /analytics/summary`, `GET /analytics/trends` | analytics |
| Forecasts & anomalies | `GET /forecasts`, `GET /anomaly-alerts`, `PATCH /anomaly-alerts/{id}` | forecasting, anomaly_detection |
| Community incidents | `GET/POST /community-incidents`, `GET/PATCH /community-incidents/{id}` | community_incidents |
| Sorting guide | `GET /material-categories`, `GET /sorting-guidance?material_category=…` | sorting_guide |
| Passports & rewards | `GET/POST /material-passports`, `POST /material-passports/{id}/custody-events`, `GET /rewards/balance`, `GET /rewards/ledger` | material_passports, rewards |
| Notifications | `GET /notifications`, `POST /notifications/{id}/read` | notifications |
| Audit & admin | `GET /audit/logs`, `GET /admin/…` | audit, administration |

## Contract tests
`tests/contract/test_api_contract.py` enforces: all application routes under `/api/v1`, documented operational endpoints, published error schema, unique operation IDs, and agreement between the backend readiness schema and the frontend's Zod schema.
