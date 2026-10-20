# Tracking (`tracking`)

Append-only vehicle position events, derived latest positions and a labelled simulator.

**Status:** implemented and tested (`backend/tests/api/test_tracking.py`). API: `docs/api/tracking-api.md`.
Design and operations: `docs/maps/GOOGLE_MAPS_INTEGRATION.md`.

## Ownership
- **Table owned:** `vehicle_location_events` (migration 0011; a trigger rejects UPDATE; indexed on vehicle and `recorded_at`).
- **Files:** `models.py`, `constants.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.

## Relationships
- Reads `fleet` (vehicles), `collection` (tasks and assignments), `route_planning` (plans and stops). Writes only its own table.

## Rules worth knowing
- Real sources (`gps_device`, `mobile_client`) must come from the collector assigned to the vehicle; `imported` is manager-only and historical; `simulator` has its own endpoints and permission and is stored in a separate group.
- Status (LIVE, DELAYED, STALE, HISTORICAL, SIMULATED, UNAVAILABLE) is computed at read time from source and timestamp; thresholds are settings (`TRACKING_*`).
- Out-of-order events are kept but never become latest; duplicates are idempotent; per-vehicle rate limit.
- Retention: `python -m app.cli purge-location-events` (schedule daily).
