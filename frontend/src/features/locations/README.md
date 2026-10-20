# Feature: locations

Locations and zones: named service areas and the facilities that belong to each.

**Status:** implemented (see `docs/ui/screen-inventory.md`). Backend module: `facilities` (`/api/v1/zones`, `GET /api/v1/facilities?zone_id=`).

- Zones have **no boundary geometry**: the platform has no verified map data, so the screen is a list and says so. There is no map and no coverage figure.
- `useZoneOptions` (exported) feeds the zone picker of the facility form.
- Server data goes through the shared API client and TanStack Query; no local mock data.
