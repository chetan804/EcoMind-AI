# Offline map tiles (not in Git)

Put the regional vector-tile file here as `region.pmtiles`. It is git-ignored and docker-ignored because it is large (tens to hundreds of MB).
Create it with `python scripts/maps/prepare_offline_maps.py tiles ...`; see `docs/maps/OFFLINE_MAPS.md`. Without the file the app still draws markers and routes on a plain background and says the base map is not installed.
