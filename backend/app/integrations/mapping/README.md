# Integration: Mapping (road routing providers)

Road-routing adapter used by `route_planning` (`GET /api/v1/route-planning/plans/{id}/road-route`).

* `base.py`: `RoadRouteProvider` protocol and result types (`RoadRoute`, `RoadRouteUnavailable`).
* `factory.py`: chooses the provider from `ROUTING_PROVIDER` (`none|google|osrm`).
* `osrm.py`: optional adapter for an OSRM server the operator runs (`OSRM_BASE_URL`), off by default, mocked tests only.
* `google_routes.py`: Google Routes API `computeRoutes` adapter. Server-side key only
  (`GOOGLE_MAPS_SERVER_API_KEY`), `TRAFFIC_UNAWARE`, field-masked, chunked to 10 intermediate
  waypoints per request, nothing cached or stored, injectable transport for tests.

**Status:** implemented and unit-tested against a mocked transport. **Not verified against the live
API** (no key and no network path to Google in the development sandbox); see
`docs/maps/GOOGLE_MAPS_INTEGRATION.md`.

Rules: integrations are called by module services, never by routers directly; they hold no business
rules and no database tables. Geocoding and Places are intentionally not integrated: addresses are
entered by users and coordinates are picked on the map.
