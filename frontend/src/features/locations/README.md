# Feature: locations

Locations and zones: named service areas and the facilities that belong to each.

**Status:** implemented (see `docs/ui/screen-inventory.md`). Backend module: `facilities` (`/api/v1/zones`, `GET /api/v1/facilities?zone_id=`).

- Zones have **no boundary geometry**: the platform has no verified boundary data, so no polygon or coverage figure is drawn. The screen shows the facilities of the selected zone on the shared map (`features/maps`; a labelled list when Google Maps is not configured) and says that zones have no boundary.
- `useZoneOptions` (exported) feeds the zone picker of the facility form.
- Server data goes through the shared API client and TanStack Query; no local mock data.
