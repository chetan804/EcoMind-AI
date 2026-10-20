# Route planning API

Base path `/api/v1/route-planning`. Bearer authentication; standard error envelope. Reading needs `routes:read` (collectors, managers, administrators); planning needs `routes:manage` (managers, administrators).

| Method and path | Purpose |
|---|---|
| `GET /route-planning/plans` | Paginated plans (filter `status`, `date_from`, `date_to`; sort) |
| `POST /route-planning/plans` | Order collection tasks for one vehicle; stored as a `draft` (`201`) |
| `GET /route-planning/plans/{id}` | Plan with ordered stops and leg distances |
| `POST /route-planning/plans/{id}/publish` | `draft → published` |
| `POST /route-planning/plans/{id}/cancel` | `draft|published → cancelled` (optional `reason`) |

## What a plan is

A **proposal**: the visiting order that minimises total straight-line distance for one vehicle that leaves a start facility (depot), visits every task, optionally ends at a facility (e.g. disposal), and returns to the depot. A plan never changes the tasks it orders; assigning and executing work stays in the Collections API. `in_progress` and `completed` exist as plan statuses but are not driven by this version.

Request: `name`, `planned_date` (today or later), `start_facility_id` (required), `end_facility_id` (optional), `task_ids` (1–40, unique), optional `vehicle_id`, `driver_id`. Unknown fields are `422`.

## Rules

* Facilities must exist, be `active` and have coordinates (`422`).
* Tasks must exist (`422`), be `pending` or `assigned` (`409 task_not_plannable`), have coordinates (`422`), and not already be in a `draft`, `published` or `in_progress` plan (`409 task_already_planned`).
* A vehicle must be `available` or `in_service` (`409 vehicle_unavailable`). If the **known** waste-report weight estimates of the tasks exceed its capacity: `409 capacity_exceeded`. Tasks without an estimate are not counted and a `warnings` entry says so; with no vehicle a warning says capacity was not checked.
* `driver_id` must be an active user who can execute collection tasks (`422`).

## Algorithm and its evidence

`route-order 1.0.0`: exact Held-Karp dynamic programming up to 12 stops (provably optimal for the matrix used); above that nearest neighbour + 2-opt + Or-opt with 24 seeded random restarts (deterministic; not guaranteed optimal). The method is recorded in `optimizer`, e.g. `route-order 1.0.0 (exact_held_karp)`.

Validation on a real benchmark (Kalasin University campus, Thailand; five observed days; `scripts/ml/ksu_route_validation.py` → `docs/ml/dataset-research/experiments/route-validation-ksu.json`), evaluated on **real road distances**:

| | mean length ÷ exact optimum |
|---|---|
| Route actually driven | 1.096 (range 1.004–1.217) |
| Nearest neighbour | 1.173 |
| `route-order` heuristic given road distances | 1.000 (matched the exact optimum on all 5 days) |
| `route-order` plan from straight-line distances only (what this API does) | 1.028 (range 1.000–1.079) |

So with the same road matrix the heuristic found the optimum on every day; planning from coordinates alone costs about 3% extra road distance on average on this campus. Five days on one small campus is indicative, not statistically strong, and says nothing about city-scale networks.

## What is *not* modelled

Stop order and the `distance_*` figures use great-circle (haversine) distances, **not** road distances (see "Road route" below for the provider-based road geometry): they are usually shorter than the road distance but not always (9 of 253 pairs in the benchmark were longer). No road network, one-way streets, traffic, time windows, driver hours, multiple trips or per-stop service time are modelled, and **no travel time or ETA is estimated** (`estimated_duration_min` stays null): the platform has no sourced speed data. The response `basis` field repeats this.

## Audit events

`route_plan.created`, `route_plan.published`, `route_plan.cancelled`.

## Road route (provider geometry, optional)

`GET /api/v1/route-planning/plans/{id}/road-route` (`routes:read`). Asks the routing provider (Google Routes API,
driving, **without live traffic**) for road geometry, distance and duration of the plan's stops in the stored order.
The platform does not re-optimise the order for road distance. Nothing is stored or cached server side, and each call can
be billed by the provider (one request per 10 stops), so clients call it on demand.

Always answers `200`:

| Field | Meaning |
|---|---|
| `available` | `true` only with real provider geometry |
| `provider` | `google_routes` when available |
| `encoded_polylines` | one encoded polyline per request chunk (decode with the Google polyline algorithm) |
| `distance_m`, `duration_s` | provider estimates (free-flow; not a promised arrival time) |
| `request_count` | provider requests made |
| `reason`, `detail` | when `available` is false: `not_configured`, `too_few_points`, `access_denied`, `quota_exceeded`, `provider_error`, `timeout`, `network_error`, `bad_response`, `no_route` |
| `basis` | plain-language statement of what the numbers are |

When `available` is false the UI draws straight lines labelled "not roads". Configuration: `GOOGLE_MAPS_SERVER_API_KEY`, see
`docs/maps/GOOGLE_MAPS_INTEGRATION.md`. Not yet verified against the live service.

