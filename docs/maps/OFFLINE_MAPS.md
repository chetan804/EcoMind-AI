# Offline maps (the default; no API key, no run-time third party)

Status at 2026-10-21: **implemented; rendering verified in headless Chromium (software WebGL) against a
synthetic tile file; not verified with real OpenStreetMap tiles** (the build sandbox cannot reach any tile
source). Real tiles need the one-off, owner-run step below.

## What it is

| Part | Choice | Licence | Where |
|---|---|---|---|
| Map engine | MapLibre GL JS 6.15 (bundled, own web worker) | BSD-3-Clause | `frontend/src/features/maps` |
| Tile container | PMTiles 4.5 (one static file, read with HTTP Range) | BSD-3-Clause | `deployment/map-data/region.pmtiles` |
| Basemap style | `@protomaps/basemaps` layers with our own palette (`ROAD_MAP_FLAVOR`) | BSD-3-Clause | `lib/offline-style.ts` |
| Map data | OpenStreetMap, as Protomaps vector tiles | ODbL 1.0, **attribution shown on every map** | the tile file |
| Fonts, sprites | Noto Sans glyphs, Protomaps sprites | OFL 1.1, MIT | `frontend/public/map-assets/` (see its README) |
| Clustering | supercluster 9 | ISC | |

Nothing is requested from a third party in the browser: tiles, fonts, sprites and the worker all come from
the same origin as the app (the production CSP needs no extra host for this provider).

It is an **original** road-map style on OpenStreetMap data. It is not Google Maps, does not use Google data or
Google styling, and makes no claim of being identical to it (Google's terms do not allow copying its map).

## Choosing the engine

`VITE_MAP_PROVIDER` (build time): `offline` (default), `google`, or empty. Empty means `offline`, or `google`
when `VITE_GOOGLE_MAPS_API_KEY` is set. See `docs/maps/GOOGLE_MAPS_INTEGRATION.md` for the Google option.

## States you can see

| State | What the user sees |
|---|---|
| Tile file installed | basemap + markers, clusters, routes, scale bar, attribution |
| Tile file missing | plain background + markers/routes + the notice "Base map not installed" (overlays stay correct) |
| Browser without WebGL | "Map not available: this browser cannot draw the map" and the labelled list of the same data |
| Code chunk failed to load | labelled error with a Retry button and the list |

A missing tile file never produces a fake map and never blocks the screens. Every map has a list view of the
same data.

## Installing real tiles (owner-run, once per region)

1. Install the `pmtiles` command line tool (https://github.com/protomaps/go-pmtiles/releases).
2. Pick a bounding box and a Protomaps build (https://maps.protomaps.com/builds lists the daily v4 builds, compatible with the `@protomaps/basemaps`
   style used here; BLAKE3 hashes are published per build; Protomaps asks users not to hotlink, which is why this
   step copies a cut-out to your own storage once instead of the app reading it live):

   ```bash
   python scripts/maps/prepare_offline_maps.py tiles \
     --bbox 78.2,17.2,78.7,17.6 \
     --source <URL of a build listed on that page> \
     --maxzoom 15
   ```

   (`--dry-run` prints the command. `--source` also accepts a local `.pmtiles` file.) The extract reads only
   the needed byte ranges; a city region is typically tens of MB.
3. The file is written to `deployment/map-data/region.pmtiles` (git-ignored and docker-ignored).
   - **Dev server (`npm run dev`) and `vite preview`**: served automatically at `/map-assets/tiles/` from
     `MAP_DATA_DIR` (default `../deployment/map-data`). No rebuild; reload the page.
   - **Docker Compose dev**: `./deployment/map-data` is mounted at `/map-data`.
   - **Production image**: mount the folder read-only into nginx
     (`-v ./deployment/map-data:/usr/share/nginx/html/map-assets/tiles:ro`). The file must be readable by the
     unprivileged nginx user (uid 101): `chmod 644`, folder `755`. nginx serves ranges for static files.
4. Update the tiles whenever you want fresher data by repeating step 2 (the basemap is a snapshot; there is
   no live OSM connection).

`VITE_MAP_TILES_URL` points to another location if the file is hosted elsewhere on your own infrastructure.

## More font ranges

The repository ships the Latin glyph ranges only (Noto Sans, 864 KB in total). Labels in other scripts
(Devanagari is referenced by the style; Telugu, Tamil, Arabic and so on) need their glyph files:
`python scripts/maps/prepare_offline_maps.py assets --all-ranges` copies all ranges (about 12 MB) from
`protomaps/basemaps-assets`. The style asks for English names (`name:en`) first, so Latin labels work out of
the box wherever OSM has them. Which non-Latin fonts the upstream repository provides is not verified here.

## What was and was not verified

Verified (local, 2026-10-20): in Chromium with SwiftShader WebGL, using `tests/e2e/visual/make-synthetic-tiles.py`
tiles (invented geometry, **not a map**): the PMTiles protocol over Range requests, worker, style, glyphs,
sprites, markers, clustering, planned/recorded/simulated paths, scale and attribution; in both the Vite dev
server and the production build. Screenshots with this caveat: `docs/ui/evidence/maps-offline/`. Unit and
component tests cover provider selection, the loader states and the overlay logic (jsdom has no WebGL, so those
use a fake engine). The Playwright tracking spec passes with this provider.

Not verified: how a real OSM region looks with this style (labels, density, performance at city scale), the
`prepare_offline_maps.py tiles` network step (needs the owner's network and the `pmtiles` CLI), the nginx
`/map-assets/` location (no nginx or Docker in the sandbox; CI builds the image), and non-Latin labels.

## Limits

- Offline means a snapshot of OSM data you chose; roads and places change, so refresh periodically.
- No geocoding or place search (addresses are typed, positions are picked on the map) and no turn-by-turn
  routing; see the optional routing adapters in `docs/maps/GOOGLE_MAPS_INTEGRATION.md`.
- Software-rendered WebGL (headless, remote desktops) is slow; the list view is always available.
