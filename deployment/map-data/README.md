# Offline map tiles (not in Git)

Put the regional vector-tile file here as `region.pmtiles`. It is git-ignored and docker-ignored because it is large (tens to hundreds of MB).

Three ways to create it (both owner-run; see `docs/maps/OFFLINE_MAPS.md`):

* Protomaps/OpenStreetMap extract: `python scripts/maps/prepare_offline_maps.py tiles ...`
* OpenStreetMap via Geofabrik + Planetiler (also prepares OSRM routing data): `docs/maps/HYDERABAD_DATA_RUNBOOK.md`
* MapTiler regional dataset (MBTiles, OpenMapTiles layout), after accepting its licence terms:
  `python scripts/maps/mbtiles_to_pmtiles.py hyderabad.mbtiles` writes `region.pmtiles` here.
  The free on-premises tier is for evaluation / non-commercial use; keep its attribution on the map.

Without the file the app still draws markers and routes on a plain background and says the base map is not installed. `docs/maps/hyderabad-aoi.geojson` is only an approximate area of interest, not tile data.
