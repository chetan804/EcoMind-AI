# Facilities API

Base path `/api/v1/facilities`. Bearer authentication; standard error envelope.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /facilities` | `facilities:read` | Paginated list, filter, search, sort |
| `GET /facilities/{id}` | `facilities:read` | One facility |
| `POST /facilities` | `facilities:manage` | Create (`201`) |
| `PATCH /facilities/{id}` | `facilities:manage` | Partial update |

`facilities:read` is held by every role (citizens use it to find drop-off points); `facilities:manage` by managers and administrators only. There is **no DELETE** (`405`): a facility is retired with `{"status": "inactive"}` so that tasks, routes and passports that reference it keep their history.

## Fields

`code` (unique, 2-32 chars `A-Z 0-9 - _`, stored upper-case, **immutable**), `name` (2-200), `facility_type` (`processing_center|depot|transfer_station|drop_off_point`), `status` (`active|inactive|maintenance`, default `active`), `address_line`, `city`, `region`, `country_code` (ISO 3166-1 alpha-2, stored upper-case), `latitude` + `longitude` (WGS84, both or neither), `daily_capacity_kg` (> 0), `contact_email`.

Unknown or read-only fields (`id`, `created_at`, and `code` on update) are rejected with 422. A duplicate code, in any letter case, is `409 facility_code_taken`.

## Privacy: `contact_email`

It may be a personal address, so it is returned **only to callers with `facilities:manage`**; for everyone else the field is `null` in both the list and the detail response, and it is never written to the audit log (only `{"changed": true}`).

## Partial update

Only the fields present in the body change. Nullable fields can be cleared with `null`; `name`, `facility_type` and `status` cannot (422). Setting only one of `latitude`/`longitude` is `422 unprocessable`. A request that changes nothing writes nothing and creates no audit entry. Otherwise the audit entry `facility.updated` records `{field: {from, to}}`. The row is locked during the update.

## Listing

`GET /facilities?page=1&page_size=25&facility_type=depot&status=active&city=Hyderabad&q=north&sort_by=name&order=asc`

`city` is a case-insensitive exact match. `q` is a case-insensitive substring over name, code and city (wildcards literal, max 100 characters). `sort_by`: `name|code|city|daily_capacity_kg|created_at` (default `name` ascending; names sort case-insensitively; ties broken by id). Invalid enum or sort values are 422.

## Audit events

`facility.created`, `facility.updated`.
