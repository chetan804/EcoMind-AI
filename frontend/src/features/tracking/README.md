# Feature: tracking

Live vehicle positions and the planned/recorded path of a collection task, drawn on the shared map surface (`features/maps`). Backend module: `tracking` (`docs/api/tracking-api.md`).

**Status:** implemented and tested with a simulator, mocked transports and emulated browser geolocation. **No real GPS source has been connected**, so nothing here has been shown to work with a real vehicle.

- `FleetMap`: latest known position per vehicle, with an explicit "last seen" age (`formatAge`) and a status badge (`VehicleStatusBadge`). A stale position is labelled STALE, and a stationary database coordinate is never shown as a vehicle.
- `CollectionTrackMap`: the planned stops and the recorded track of one task.
- `LocationSharing`: the collector's "Share my position" control (browser geolocation, only while the tab is open, at most one report per 15 s).
- `SimulationControls`: manager-only demonstration simulator. Simulated positions are always labelled and kept apart from real events.
- Polling only (15 s, backing off to 120 s); no WebSocket or SSE. Hooks in `hooks/useTracking.ts`.
- Public interface: `import { FleetMap, CollectionTrackMap, LocationSharing, SimulationControls } from '@/features/tracking'`.
