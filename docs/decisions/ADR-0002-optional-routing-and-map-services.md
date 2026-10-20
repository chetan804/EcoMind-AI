# ADR-0002: Offline map by default; optional external routing services

- **Status:** Accepted
- **Date:** 2026-10-21

## Context
The product needs maps and, for route plans, road geometry. The owner wants maps that work without an API key
and without a run-time dependency on a third party, at production quality and with clean licences. Google's
terms do not allow copying its map, so "exactly like Google Maps" is not possible; an equivalent-purpose map
built on OpenStreetMap data is.

## Decision
1. **Maps:** the default provider is a built-in offline map (MapLibre GL JS + a PMTiles file the owner
   prepares once from OpenStreetMap data; fonts and sprites ship with the app). Google Maps stays as an opt-in
   provider (`VITE_MAP_PROVIDER=google` or a browser key). See `docs/maps/OFFLINE_MAPS.md`.
2. **Road routing:** `ROUTING_PROVIDER=none|google|osrm`, default `none` (labelled straight lines; stop order
   always comes from the platform's own optimiser). `osrm` calls an OSRM server the operator runs
   (`OSRM_BASE_URL`); `google` uses the Routes API with a server-only key. See `docs/maps/ROUTING_PROVIDERS.md`.
3. Both adapters sit behind the existing `RoadRouteProvider` protocol (`backend/app/integrations/mapping`).
   Nothing is stored, no business rule lives in an adapter, and a failure is reported with a reason, never
   as an invented route.

## Deviation from the locked architecture, and why it is acceptable
The locked stack has no extra services. OSRM is a **separate process** (not a Python dependency) and so is a
deviation, but only if an operator opts in: it is off by default, the platform runs, is tested and deployed
without it, and there is no queue, cache or database shared with it. The offline map adds no service at all
(static files).

## Alternatives considered
- **Self-host a tile server (Tileserver GL, Martin) + Valhalla/OSRM by default:** rejected; more services to run
  and secure than the product needs; a static PMTiles file removes the tile server.
- **Public OSM tile servers or the OSRM demo server:** rejected for production (usage policies forbid heavy or
  production use; adds a third-party run-time dependency).
- **Google only:** rejected as the default (needs a key and billing, third-party dependency, licence limits).
- **PostGIS / pgRouting in the database:** rejected; would change the locked database setup and still needs road
  data imports.

## Consequences
- The basemap is a snapshot that the owner refreshes; there is no geocoding or turn-by-turn navigation.
- Offline rendering depends on WebGL; every map has a list view as the fallback.
- The OSRM adapter is verified against a mocked transport only (no OSRM server in the build sandbox).

## Migration plan
Switching provider is configuration only (`ROUTING_PROVIDER`, `VITE_MAP_PROVIDER`). Removing OSRM later means
deleting `osrm.py`, the factory branch and the three settings; no data or schema is involved.

## Review triggers
A measured need for geocoding, live traffic or turn-by-turn guidance; tile data too large for one file.
