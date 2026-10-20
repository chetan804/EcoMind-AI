# Offline map evidence (synthetic tiles)

Real Chromium screenshots (software WebGL) of the built-in offline map, captured on 2026-10-20 with
`tests/e2e/visual/capture-maps.mjs`. They prove the **pipeline**: tile protocol (PMTiles over HTTP Range),
MapLibre worker, vector style, vendored fonts and sprites, markers, clustering, paths, scale and attribution
in the dev server and in the production build (`fleet-production-build.png`).

**The basemap in these images is not a map of anywhere.** The tiles were produced by
`tests/e2e/visual/make-synthetic-tiles.py` (an invented lake, park, road grid and three place names named
"Synthetic Town ..."). The markers and routes are synthetic demonstration records. These images do **not**
show how a real OpenStreetMap region looks, and they are not evidence of similarity to any other map product.
Real tiles need the owner-run step in `docs/maps/OFFLINE_MAPS.md`.
