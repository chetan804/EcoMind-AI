# Tracking API

Base path `/api/v1/tracking`. Bearer authentication; standard error envelope. Positions are **append-only
events**; "latest position" is computed from them. No vehicle has a stored coordinate.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /tracking/config` | `fleet:read` | thresholds, retention, whether the simulator is enabled, whether road routing is configured |
| `GET /tracking/vehicles?include_simulated=` | `fleet:read` | latest position per vehicle with status; real and simulated rows are separate items |
| `GET /tracking/vehicles/{id}` | `fleet:read` | the same for one vehicle |
| `GET /tracking/vehicles/{id}/locations` | `fleet:read` | paginated event history (real sources only) |
| `POST /tracking/vehicles/{id}/locations` | `fleet:track` or `fleet:manage` | report a position (`201`; `200` if it is a duplicate) |
| `POST /tracking/simulation/vehicles/{id}/locations` | `fleet:simulate` | write a simulator event (`201`) |
| `DELETE /tracking/simulation/vehicles/{id}/locations` | `fleet:simulate` | remove the vehicle's simulator events only |
| `GET /tracking/collections/{task_id}` | `collection:read`, and `collection:manage` or the active assignee | planned point, vehicle position, path linked to the task |
| `GET /tracking/route-plans/{id}` | `routes:read` | stops with their real task state, vehicle position, recorded path |

## Reporting a position

Body (`extra` fields are rejected): `latitude`, `longitude` (6 decimals max), `recorded_at` (timezone-aware),
`source` (`gps_device`, `mobile_client`, `imported`), optional `accuracy_m`, `speed_kph`, `heading_deg`
(only if the device measured them), `sequence`, `collection_task_id`, `route_plan_id`.

Authorisation: live sources (`gps_device`, `mobile_client`) need `fleet:track` **and** the caller must be the collector
currently assigned to the vehicle through an open task (`403 not_assigned_to_vehicle` otherwise). `source=imported` needs
`fleet:manage` and `recorded_at` must be older than the stale threshold (900 s), so an import can never pose as a live position.

Rejections: `422` for `source=simulator` on this endpoint, `0,0`, out-of-range or over-precise coordinates,
`recorded_at` more than 120 s in the future or, for non-imported sources, older than 6 h, a task or plan that
does not exist or does not use this vehicle (live reports must link to an in-progress task of the caller);
`404` unknown vehicle; `409 vehicle_retired`; `429` with `Retry-After: 10` above 30 events per vehicle per minute.

Ordering: an event older than the newest existing event of its group (real or simulator) is stored with
`quality=out_of_order` and is never the latest position. A repeat of the same `(vehicle, recorded_at)` or the
same `sequence` returns the original event with `duplicate=true` (`200`). Real and simulator events are ordered separately.

## Status of a position (derived at read time)

| Status | Meaning |
|---|---|
| `live` | real source, reported within `live_within_seconds` (120) |
| `delayed` | real source, older than that but within `stale_after_seconds` (900) |
| `stale` | real source, older than that |
| `historical` | imported track |
| `simulated` | simulator source |
| `unavailable` | the vehicle has no event at all (no position is returned) |

Without `fleet:manage`, a caller sees only vehicles they are currently assigned to (others are `404`). Route
tracking hides the vehicle and path unless the caller is `fleet:manage` or assigned to the vehicle. Collection tracking
is limited to managers and the active assignee. Real and simulated rows are always separate items.

## Audit events

`tracking.location_imported` (each import), `tracking.simulation_reset`, `tracking.retention_purge`. Live reports and
simulator writes are not audited one by one (volume): the events are themselves the record, with source and user.

Configuration: `TRACKING_*` variables in `backend/.env.example`. Retention: `python -m app.cli purge-location-events`.
