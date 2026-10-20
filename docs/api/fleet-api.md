# Fleet API

Base path `/api/v1/fleet`. Bearer authentication; standard error envelope.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /fleet/vehicles` | `fleet:read` | Paginated list, filter, search, sort |
| `GET /fleet/vehicles/{id}` | `fleet:read` | One vehicle |
| `POST /fleet/vehicles` | `fleet:manage` | Register a vehicle (`201`) |
| `PATCH /fleet/vehicles/{id}` | `fleet:manage` | Partial update |

`fleet:read` is held by collectors, facility operators, managers and administrators; citizens have no access (`403`). `fleet:manage` is held by managers and administrators. There is **no DELETE**: a vehicle is retired with `{"status": "retired"}` so assignments and history keep their reference.

## Fields

`registration_number` (4-32 characters: letters, digits, spaces, `-`; stored upper-case; unique; **immutable**), `vehicle_type` (`compactor_truck|tipper_truck|van|cargo_bike|other`), `status` (`available|in_service|maintenance|retired`, default `available`), `capacity_kg` (> 0, ≤ 1,000,000, 3 decimals), `home_facility_id` (optional facility).

Responses add `active_task_count` (tasks in `assigned` or `in_progress` using the vehicle), `created_at`, `updated_at`. Unknown or read-only fields are `422`.

## Rules

* A duplicate registration, in any letter case, is `409 vehicle_registration_taken`.
* A vehicle with active tasks cannot be moved to `maintenance` or `retired`: `409 vehicle_in_use`.
* A vehicle in `maintenance` or `retired` cannot be assigned to a task (`409 vehicle_unavailable`, see the Collections API).
* A request that changes nothing writes nothing and creates no audit entry.

## Listing

`GET /fleet/vehicles?page=1&page_size=25&status=available&vehicle_type=van&q=ab12&sort_by=registration_number&order=asc`

`sort_by`: `registration_number|capacity_kg|status|created_at`. Invalid enum or sort values are `422`.

## Audit events

`vehicle.created`, `vehicle.updated`.
