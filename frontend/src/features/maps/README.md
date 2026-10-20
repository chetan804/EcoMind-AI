# Maps (`features/maps`)

The shared map layer. Every screen with a map uses `MapPanel`; nothing else imports Google Maps.

* `MapPanel`: Google map with markers (advanced markers), clustering, paths, legend, detail panel,
  and an accessible list of the same items. Renders a labelled list fallback when there is no key,
  the script cannot load, the key is rejected, or the API times out. It never renders a blank map.
* `LocationPicker`: click-to-pick, typed coordinates, optional device location (only on a button
  press). Works without Google Maps.
* `lib/google-loader.ts`: loads the Maps JavaScript API once, on demand, classifying failures.
* `lib/polyline.ts`, `lib/geo.ts`: pure helpers (polyline decoding, distance, deterministic
  simulation points, directions URL). Unit-tested.
* `types.ts`: `GeoPoint`, `MapMarker`, `MapPath`, `LegendEntry` shared by all maps.

Configuration: `VITE_GOOGLE_MAPS_API_KEY` (public, referrer-restricted) and optional
`VITE_GOOGLE_MAPS_MAP_ID`, read only in `app/config.ts`. See `docs/maps/GOOGLE_MAPS_INTEGRATION.md`.

Rules: markers must never carry private data (reporter identity, home addresses) in their title or
details; a stationary database coordinate is never drawn as a live vehicle (see `features/tracking`);
straight lines between stops are drawn dashed and labelled as such, never as roads.
