# Maps (`features/maps`)

The shared map layer. Every screen with a map uses `MapPanel`; nothing else imports a map engine.
`MapPanel` picks the engine from `VITE_MAP_PROVIDER` (see `docs/maps/OFFLINE_MAPS.md`): the **offline**
engine is the default and needs no API key; Google Maps is optional.

* `MapPanel`: chooses the engine and renders the same markers, clustering, paths, legend, detail panel
  and accessible list of the same items on either. It renders a labelled list fallback when the engine
  cannot start, the key is rejected, or loading times out. It never renders a blank map.
* `OfflineMapPanel` / `MapLibreSurface`: MapLibre GL JS reading one PMTiles file from the same origin
  (`/map-assets/tiles/region.pmtiles`). No third party is contacted from the browser.
  * `lib/offline-loader.ts`: probes the tile file, reads its `vector_layers`, and decides the layout.
  * `lib/tile-schema.ts`: recognises **Protomaps** (`earth` + `roads`) or **OpenMapTiles**
    (`transportation` + `place` + `water`, e.g. a MapTiler regional MBTiles converted with
    `scripts/maps/mbtiles_to_pmtiles.py`); anything else says "Base map file not recognised".
  * `lib/offline-style.ts`, `lib/openmaptiles-style.ts`: our own road-map style for each layout.
* `GoogleMapPanel` / `GoogleMapSurface` / `lib/google-loader.ts`: optional Google engine, loaded once
  on demand, failures classified.
* `LocationPicker`: click-to-pick, typed coordinates, optional device location (only on a button
  press). Works without any map engine.
* `lib/polyline.ts`, `lib/geo.ts`: pure helpers (polyline decoding, distance, deterministic
  simulation points, directions URL). Unit-tested.
* `types.ts`: `GeoPoint`, `MapMarker`, `MapPath`, `LegendEntry` shared by all maps.

Configuration (read only in `app/config.ts`): `VITE_MAP_PROVIDER`, `VITE_MAP_TILES_URL`, and for
Google `VITE_GOOGLE_MAPS_API_KEY` (public, referrer-restricted) and optional `VITE_GOOGLE_MAPS_MAP_ID`.
See `docs/maps/OFFLINE_MAPS.md` and `docs/maps/GOOGLE_MAPS_INTEGRATION.md`.

Rules: markers must never carry private data (reporter identity, home addresses) in their title or
details; a stationary database coordinate is never drawn as a live vehicle (see `features/tracking`);
straight lines between stops are drawn dashed and labelled as such, never as roads. Attribution
("© OpenStreetMap contributors", plus "© MapTiler" for MapTiler data) is shown on every offline map.
