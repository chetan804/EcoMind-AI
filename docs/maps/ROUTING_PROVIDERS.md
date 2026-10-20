# Road routing providers

Status at 2026-10-21: all providers verified against **mocked transports only** (no Google key, no OSRM server
in the build sandbox). Decision record: `docs/decisions/ADR-0002-optional-routing-and-map-services.md`.

Road routing is optional. Without it the product works: route plans show straight lines labelled "not a
driving route" and distances are straight-line estimates. The **stop order** never depends on a provider (it is
set by the platform's optimiser, `route-order 1.0.0`); a provider only supplies road geometry, distance and a
free-flow duration for the already chosen order.

## Configuration (server side, `backend/.env.example`)

| Variable | Meaning |
|---|---|
| `ROUTING_PROVIDER` | `none`, `google` or `osrm`. Empty keeps the earlier behaviour: `google` if `GOOGLE_MAPS_SERVER_API_KEY` is set, otherwise `none`. |
| `OSRM_BASE_URL` | Base URL of **your** OSRM server, e.g. `http://osrm:5000`. Plain `http(s)`, no credentials, query or fragment. Required when `ROUTING_PROVIDER=osrm`. |
| `OSRM_TIMEOUT_SECONDS` | Default 8. |
| `GOOGLE_MAPS_SERVER_API_KEY`, `GOOGLE_ROUTES_TIMEOUT_SECONDS` | See `GOOGLE_MAPS_INTEGRATION.md`. |

Misconfiguration fails at startup (`osrm` without a URL, `google` without a key, a bad URL).
`GET /api/v1/tracking/config` reports `road_routing_configured` (true when a provider other than `none` is in
force).

## OSRM (optional external service you operate)

- **What:** Open Source Routing Machine, BSD-2-Clause, run against an OpenStreetMap extract you choose. The
  adapter calls `GET {OSRM_BASE_URL}/route/v1/driving/{lng,lat;...}?overview=full&geometries=polyline`
  (`backend/app/integrations/mapping/osrm.py`), one request per plan, no redirects followed, response capped
  at 5 MB, nothing cached or stored.
- **Not provided here:** an OSRM container or a data extract. Build one with the OSRM documentation (extract,
  partition, customize, `osrm-routed`) and keep it on a private network reachable only by the backend. The
  public OSRM demo server is not for production use and is never a default.
- **Results:** distance and duration from the OSRM `car` profile (free-flow estimates, no traffic) and
  labelled as such in the UI.
- **Failure reasons** (same set as Google): `not_configured`, `too_few_points`, `no_route` (`NoRoute`,
  `NoSegment`), `provider_error` (HTTP 400/5xx or any other OSRM code, such as a too-large query),
  `access_denied`, `quota_exceeded`, `timeout`, `network_error`, `bad_response`.
- **Verified:** 28 unit tests with a mocked transport (URL shape and lng/lat order, success mapping, every
  failure reason, settings validation and provider choice), plus the `/tracking/config` flag.
- **Not verified:** a live OSRM server (and therefore real geometry, polyline precision against a live answer,
  and server-side limits such as `--max-viewroute-size`). Do this once after deployment: open a route plan and
  confirm the blue road line follows streets and that distance and duration are plausible.

## Google Routes API

See `GOOGLE_MAPS_INTEGRATION.md` (server-only key, `TRAFFIC_UNAWARE`, chunked at 10 intermediates, nothing stored,
not verified live).

## Adding a provider

Implement `RoadRouteProvider` (`integrations/mapping/base.py`), return `RoadRoute` or `RoadRouteUnavailable`
with one of the existing reasons, register it in `integrations/mapping/factory.py`, add a settings value and
tests with an injectable transport. Encoded polylines must use precision 5.
