# Runbook: offline map tiles and road routing for Hyderabad (owner-run)

Goal: replace the placeholder background with real OpenStreetMap tiles for Hyderabad, and optionally give route
plans real road geometry, **without any API key and without a run-time third party**. Everything below runs on a
machine you control. The application itself never downloads map data.

> **Status of this runbook.** The commands and the helper script were written from the tools' own documentation
> (Geofabrik, Planetiler, OSRM READMEs, fetched 2026-10-21) and their option handling is covered by 53 automated
> tests. **Planetiler, osmium and OSRM have not been run by the author, and no real Hyderabad output exists yet**:
> the build environment has no Docker or Java and cannot reach Geofabrik. The first real run is yours; the
> `check-*` steps below tell you objectively whether it worked.

Two ways to obtain tiles. Pick one:

| | A. Build from OpenStreetMap (this runbook) | B. MapTiler regional dataset |
|---|---|---|
| Source | Geofabrik `.osm.pbf` + Planetiler | MBTiles from your MapTiler account |
| Licence | ODbL data; free for any use with attribution | Free tier: evaluation / non-commercial, 100 monthly users (see [`OFFLINE_MAPS.md`](OFFLINE_MAPS.md)) |
| Effort | Several GB of downloads, 10–60+ minutes of CPU | One download (needs your account) |
| Also gives routing data | Yes (same `.osm.pbf`) | No |

Both end in the same file, `deployment/map-data/region.pmtiles`, and the app reads either (it detects the schema).
Route A is the better fit for anything beyond a supervised demonstration, because its licence does not limit
users or commercial use.

## 0. Prerequisites

| Need | For | Notes |
|---|---|---|
| Python 3.11+ | every step | `pip install --require-hashes -r scripts/maps/requirements.lock` (the PMTiles writer) |
| Docker | Planetiler and OSRM (default runner) | Or, for Planetiler only, Java 25+ with the jar (`--runner jar --planetiler-jar planetiler.jar`) or the `planetiler` launcher (`--runner binary`); see the [Planetiler README](https://github.com/onthegomap/planetiler) |
| `osmium-tool` | optional `crop` step | `apt install osmium-tool` / `brew install osmium-tool` |
| Disk | tiles | Planetiler's guidance: at least 1 GB plus 5–10× the `.osm.pbf` size. The Southern Zone file is about 532 MB (Geofabrik, 2026-10-20), so plan for roughly 4–7 GB free, plus about 1 GB of support data on the first run |
| RAM | tiles | About half the `.osm.pbf` size for the JVM (the script sets this) |
| RAM | routing | `osrm-extract` on a country- or zone-sized file needs several GB and can take a long time (OSRM's README reports about 30 minutes for a 550 MB file). **Crop to the city first** (step 3) |
| Network | download | Geofabrik, `ghcr.io`, and (Planetiler `--download`) the sources it lists in its NOTICE file |

Hyderabad lies in Geofabrik's **Southern Zone** of India (`asia/india/southern-zone`); there is no city-sized
Geofabrik extract. The area of interest is [`hyderabad-aoi.geojson`](hyderabad-aoi.geojson) (approximate box
78.2, 17.2, 78.65, 17.6; **not** an official boundary). The script takes its default box from that file.

Pin the tool versions for a repeatable build: `--planetiler-image ghcr.io/onthegomap/planetiler:<tag>` and
`--osrm-image ghcr.io/project-osrm/osrm-backend:<tag>`. The defaults are `latest`, which is what both projects'
READMEs show; I could not check the registries from the build environment, so choose and test a tag yourself.

## 1. Download the OpenStreetMap extract

```bash
python scripts/maps/build_region_data.py download            # add --dry-run to see the URL first
```

Downloads `https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf` into `deployment/map-build/`
(git-ignored and docker-ignored; deliberately **not** under `deployment/map-data/`, which the dev server and nginx
expose). It then compares the file with Geofabrik's published `.md5`. If that file cannot be read, the step stops
and asks for `--md5 <hash>` (from the Geofabrik page) or an explicit `--skip-md5`; a skipped check is recorded in
`osm-source.json`. Download once; Geofabrik asks for fair use of its server.

## 2. Build vector tiles (Planetiler, OpenMapTiles profile)

```bash
python scripts/maps/build_region_data.py tiles --dry-run     # prints the exact docker command
python scripts/maps/build_region_data.py tiles
python scripts/maps/build_region_data.py check-tiles         # independent validation of the result
```

`tiles` runs Planetiler (OpenMapTiles is its default profile) with `--bounds=78.2,17.2,78.65,17.6`,
`--maxzoom=14` (Planetiler's default; the app over-zooms for closer views) and `--download`, which fetches the
water-polygon and Natural Earth data that profile needs (about 1 GB on the first run). Output:
`deployment/map-build/region.mbtiles`, then the script validates it:

* `format` is `pbf` (vector tiles) and the file has tiles;
* the layers `transportation`, `place` and `water` exist (what the app's OpenMapTiles style draws);
* the bounds overlap the area of interest;
* the attribution names OpenStreetMap (the ODbL requires it).

A failure stops the pipeline with the reason. Files written by Docker may be owned by root; use `sudo chown` if you
need to delete them.

## 3. Convert to PMTiles and install

```bash
python scripts/maps/build_region_data.py pmtiles             # -> deployment/map-data/region.pmtiles
```

This re-checks the MBTiles file, then runs [`mbtiles_to_pmtiles.py`](../../scripts/maps/mbtiles_to_pmtiles.py)
(it expands the layer list, writes atomically and reads the result back). Reload the app: the Facilities and Fleet
maps now draw streets and labels. Serving details (dev server, Compose, nginx read-only mount, file permissions)
are in [`OFFLINE_MAPS.md`](OFFLINE_MAPS.md#installing-real-tiles-owner-run-once-per-region).

**Credit.** The map shows "© OpenStreetMap contributors", and "© OpenMapTiles" when the file's own attribution
names it (Planetiler's OpenMapTiles output does; the text is built by the app, never copied as markup). Keep both.
Under the ODbL you must credit OpenStreetMap; if you publish a derived *database* (the PMTiles file counts as one if
you redistribute it), it must be offered under the ODbL too. Serving the rendered map to users is a "produced work"
and needs only the credit. This is a plain-language summary, not legal advice: read
<https://www.openstreetmap.org/copyright> and <https://opendatacommons.org/licenses/odbl/>.

## 4. Optional: road routing with OSRM

Only needed if you want route plans to follow streets. Without it the app draws a labelled straight-line
sequence and says so (`ROUTING_PROVIDER=none`).

```bash
python scripts/maps/build_region_data.py crop                # osmium: cut the box out of the zone file
python scripts/maps/build_region_data.py routing --dry-run
python scripts/maps/build_region_data.py routing             # osrm-extract, osrm-partition, osrm-customize (MLD)
```

`crop` keeps whole ways that touch the box (`--strategy complete_ways`), so roads are not cut mid-segment, but
anything outside the box is gone: **routes cannot leave the cropped area**. Use a larger `--bbox` if your fleet
drives beyond the AOI. `routing` runs the three OSRM tools from OSRM's own Quick Start with the `car` profile and
writes `deployment/osrm-data/region.osrm*` (git-ignored). It stops if `region.osrm.mldgr` is missing afterwards.

Start the server on a private network and point the backend at it:

```bash
docker compose --profile osrm up -d osrm        # service defined in compose.yaml; not published to the host
# .env:  ROUTING_PROVIDER=osrm   OSRM_BASE_URL=http://osrm:5000
docker compose up -d backend
```

or, to test standalone: `docker run --rm -p 127.0.0.1:5000:5000 -v "$PWD/deployment/osrm-data:/data:ro"
ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/region.osrm`. Never use the public OSRM demo
server, and never expose `osrm-routed` to the internet.

Verify objectively:

```bash
python scripts/maps/build_region_data.py check-routing --url http://127.0.0.1:5000
```

It requests a driving route from Charminar to the HITEC City area (about 13 km apart in a straight line) and
refuses the answer unless the code is `Ok`, the road distance is at least the straight-line distance and within
8–60 km, and the travel time is plausible. Then open a route plan in the app and check by eye that the blue line
follows streets. OSRM durations are free-flow estimates without traffic, and the UI says so.

## 5. Updating

OpenStreetMap changes daily; the map is a snapshot. Repeat steps 1–4 (add `--force` where a file exists) when you
want fresher data, then replace `region.pmtiles` (reload the page) and restart `osrm`.

## What was and was not verified

| Item | Status |
|---|---|
| Geofabrik URL pattern and the Southern Zone containing Hyderabad | Read from the Geofabrik India page (2026-10-21); not downloaded |
| Planetiler options (`--osm-path`, `--output`, `--bounds`, `--maxzoom`, `--download`, `--force`, `--tmpdir`, defaults) | Read from the Planetiler README and source (`PlanetilerConfig.java`); not run (no Java or Docker here) |
| OSRM extract/partition/customize/routed commands, MLD, `ghcr.io/project-osrm/osrm-backend` | Read from OSRM's README and wiki; not run |
| Script logic: argument checks, command construction, MD5 check, tile validator, route sanity check, dry runs | **Verified** by `tests/contract/test_build_region_data.py` (53 tests, synthetic inputs, run in CI) |
| MBTiles → PMTiles conversion and the app drawing an OpenMapTiles-layout file | Verified with a synthetic fixture only (see `OFFLINE_MAPS.md`) |
| A real Hyderabad tile file: appearance, size, label density, non-Latin names, build time | **Not verified** |
| A running OSRM and real route geometry | **Not verified**; `check-routing` exists to do it |
| Docker image tags (`latest` defaults) | Not checked; pin your own |
| `compose.yaml` `osrm` service | YAML and schema validated only; the container has never been started by the author |
