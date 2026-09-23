# API reference (map & conventions)

Interactive docs: `/docs` (Swagger UI) and `/openapi.json` on any running instance —
generated from the code, always current. This page is the orientation map.

## Conventions

- Base path: `/api/v1`
- Auth: `Authorization: Bearer <access JWT>`; active organization via `X-Org-Id`
  header (validated against the user's memberships; defaults to their default org).
- Content type JSON unless noted (uploads are `multipart/form-data`).
- Errors are structured:

```json
{
  "error": { "code": "VALIDATION_ERROR", "message": "…", "details": { } },
  "request_id": "8f14e45fceea167a5a36dedd4bea2543"
}
```

Common codes: `VALIDATION_ERROR` (422), `UNAUTHORIZED` (401), `FORBIDDEN` (403),
`NOT_FOUND` (404), `RATE_LIMITED` (429), `internal_error` (500 — details only in logs).

## Endpoint map

### Auth (`/auth`)
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/register` | optionally `join_org_slug` (open orgs) |
| POST | `/login` | rate-limited (auth) |
| POST | `/refresh` | single-use rotation |
| POST | `/logout` | revokes refresh family |
| GET | `/me` | user + memberships + permissions |
| POST | `/forgot-password` · `/reset-password` | single-use tokens |
| GET | `/public/organizations` | orgs open for citizen signup |

### Organizations (`/organizations`)
`POST /` (create) · `GET /mine` · `GET/PATCH /current` · `POST /join/{slug}` ·
`GET/POST /current/units` · `GET/POST /current/zones` (GeoJSON polygons) ·
`GET /current/members` · `PATCH /current/members/{user_id}` (role/active) ·
`POST /current/invitations` · `POST /invitations/accept`

### Waste (`/waste`)
`POST /reports` (citizen) · `POST /reports/anonymous` (if org allows) ·
`GET /reports` (filters: status/severity/zone/mine/near lat+lng+radius) ·
`GET /reports/{id}` · `GET /reports/{id}/timeline` ·
`PATCH /reports/{id}/status` (triage/resolve/reject + notes) ·
`POST /reports/{id}/assign` · `GET/POST /categories`

### Complaints (`/complaints`)
`POST /` · `GET /` (status/priority/category/mine filters) · `GET /{id}` ·
`PATCH /{id}` (new_status/priority/category/assignee/resolution) ·
`GET/POST /{id}/comments` (public vs internal notes)

### Collection (`/collection`)
`GET/POST /points` · `GET/POST /schedules` · `GET /events` (date/status filters) ·
`POST /events/{id}/complete` (weight, contamination, skip reason)

### Fleet (`/fleet`)
`GET/POST /vehicles` · `PATCH /vehicles/{id}` · `GET/POST /drivers`

### Routing (`/routes`)
`POST /generate` (OR-Tools CVRP; zone/points/vehicles/driver/depot) ·
`GET /` (list) · `GET /my/today` (driver's routes) · `GET /{id}` (detail + stops) ·
`PATCH /{id}/status` (draft→approved→in_progress→completed) ·
`PATCH /stops/{stop_id}` (field execution)

### IoT (`/iot`, `/ingest`)
`GET/POST /iot/devices` (key returned once) · `POST /iot/devices/{id}/rotate-key` ·
`PATCH /iot/devices/{id}` · `GET /iot/devices/{id}/telemetry` ·
`GET/POST /iot/alert-rules` · `GET /iot/alerts` · `PATCH /iot/alerts/{id}` ·
`POST /ingest/telemetry` (**device-authenticated** via `X-Device-Key`) ·
simulator endpoints (labelled, `source=simulator`)

### AI (`/ai`)
Provider-agnostic inference endpoints; every result carries `confidence`,
`is_simulated`, and review routing for low confidence.

### Media (`/media`)
`POST /upload` (multipart; MIME allow-list, size cap) · `GET /{id}` (org-scoped)

### Sustainability (`/sustainability`)
`GET /summary?days=` (period, waste by destination, diversion, scopes, avoided) ·
`POST /recompute?days=` (permission-gated) · `GET /factors` (versioned library)

### Analytics (`/analytics`)
`GET /operations` · `GET /citizen` · `GET /executive?days=` ·
`GET /export/collections.csv` · `GET /export/reports.csv`

### Notifications / Rewards / Admin
`GET /notifications` (+`unread_only`) · `POST /notifications/{id}/read` ·
`POST /notifications/read-all` ·
`GET /rewards/me` · `GET /rewards/leaderboard` ·
`GET /admin/audit` (action_prefix filter) · `GET /admin/platform/overview`
(platform admin)

## Pagination

List endpoints return `{ "items": [...], "pagination": { "page", "page_size",
"total", "pages" } }` (some heavy lists return plain arrays — see OpenAPI).
Default page size 25, max 100.

## Versioning

The API is versioned by path (`/api/v1`). Breaking changes ship as `/api/v2` with a
deprecation window; additive changes (new optional fields, new endpoints) do not bump
the version.
