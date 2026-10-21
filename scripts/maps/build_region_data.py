#!/usr/bin/env python3
"""Build the offline map and routing data for one region from OpenStreetMap, on your own machine.

This is the owner-run pipeline behind docs/maps/HYDERABAD_DATA_RUNBOOK.md. Nothing here runs inside the
application, and nothing it produces is committed (the outputs are git-ignored and docker-ignored).

  download   Geofabrik .osm.pbf extract (default: Southern Zone of India, which contains Hyderabad),
             checked against Geofabrik's published MD5 file
  tiles      Planetiler, OpenMapTiles profile  ->  work/region.mbtiles   (needs Docker, Java 25+, or a
             `planetiler` launcher; about 1 GB of support data is downloaded on the first run)
  pmtiles    work/region.mbtiles -> deployment/map-data/region.pmtiles    (scripts/maps/mbtiles_to_pmtiles.py)
  crop       optional: cut a smaller .osm.pbf for routing with `osmium extract` (needs osmium-tool)
  routing    OSRM osrm-extract + osrm-partition + osrm-customize (MLD) -> deployment/osrm-data/region.osrm*
  check-tiles    validate a .mbtiles file (format, bounds, layers, tiles, attribution)
  check-routing  ask a running osrm-routed for a real route across the region and sanity-check the answer

Typical order (every step accepts --dry-run, which prints the exact command and runs nothing):

  python scripts/maps/build_region_data.py download
  python scripts/maps/build_region_data.py tiles
  python scripts/maps/build_region_data.py check-tiles
  python scripts/maps/build_region_data.py pmtiles
  python scripts/maps/build_region_data.py crop && python scripts/maps/build_region_data.py routing

Licences: the data is (c) OpenStreetMap contributors under the ODbL 1.0 (attribution required, share-alike
for derived databases); OpenMapTiles-schema tiles also require the "(c) OpenMapTiles" credit, which the app
shows. Geofabrik asks for fair use of its server: download once, not in a loop.

What is verified: command construction, input checks, the MD5 check, the MBTiles validator and the route
sanity check, by tests/contract/test_build_region_data.py against synthetic files. What is NOT verified:
running Planetiler or OSRM themselves, and any real Hyderabad output (the build sandbox has neither Docker,
Java nor access to Geofabrik).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AOI_FILE = ROOT / "docs" / "maps" / "hyderabad-aoi.geojson"
DEFAULT_WORK = ROOT / "deployment" / "map-build"  # not under map-data, which nginx and the dev server expose
DEFAULT_PMTILES = ROOT / "deployment" / "map-data" / "region.pmtiles"
DEFAULT_OSRM_DIR = ROOT / "deployment" / "osrm-data"
GEOFABRIK = "https://download.geofabrik.de"
DEFAULT_REGION = "asia/india/southern-zone"  # Telangana (Hyderabad) is in Geofabrik's Southern Zone
PLANETILER_IMAGE = "ghcr.io/onthegomap/planetiler:latest"
OSRM_IMAGE = "ghcr.io/project-osrm/osrm-backend:latest"
OSRM_PROFILE_IN_IMAGE = "/opt/car.lua"
OPENMAPTILES_CORE = {"transportation", "place", "water"}
# Two well-known points far apart inside the area of interest, for the routing check (lng, lat):
# Charminar (old city) and the HITEC City area. Roughly 13 km apart in a straight line.
CHECK_ROUTE = ((78.4747, 17.3616), (78.3772, 17.4435))
CHECK_ROUTE_KM = (
    8.0,
    60.0,
)  # a road route cannot be shorter than the straight line (~13 km) nor absurdly long
CHUNK = 1024 * 1024


class StepError(Exception):
    """A step cannot run or its result is not acceptable (reported without a traceback)."""


# --------------------------------------------------------------------------------------- arguments


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    """`west,south,east,north` in degrees; rejects anything that cannot be a real box."""
    try:
        west, south, east, north = (float(part) for part in value.split(","))
    except ValueError as error:
        raise StepError("--bbox needs four numbers: west,south,east,north") from error
    if not (-180 <= west < east <= 180) or not (-90 <= south < north <= 90):
        raise StepError("--bbox: west < east within -180..180 and south < north within -90..90")
    return west, south, east, north


def aoi_bbox(path: Path = AOI_FILE) -> tuple[float, float, float, float]:
    """The bounding box of the project's area-of-interest polygon (single source of truth)."""
    document = json.loads(path.read_text(encoding="utf-8"))
    points = [
        point
        for feature in document["features"]
        for ring in feature["geometry"]["coordinates"]
        for point in ring
    ]
    lngs, lats = [p[0] for p in points], [p[1] for p in points]
    return min(lngs), min(lats), max(lngs), max(lats)


def bbox_text(bbox: Sequence[float]) -> str:
    return ",".join(f"{value:g}" for value in bbox)


def validate_region(region: str) -> str:
    """A Geofabrik path such as `asia/india/southern-zone`: letters, digits, `-` and `/` only."""
    cleaned = region.strip("/")
    parts = cleaned.split("/")
    if not cleaned or any(
        not part or not all(c.isalnum() or c == "-" for c in part) for part in parts
    ):
        raise StepError("--region must look like asia/india/southern-zone")
    return cleaned


def geofabrik_url(region: str) -> str:
    return f"{GEOFABRIK}/{validate_region(region)}-latest.osm.pbf"


def jvm_memory_gb(pbf_bytes: int) -> int:
    """Planetiler's own guidance: heap of about half the .osm.pbf size, at least 1 GB."""
    return max(1, math.ceil(pbf_bytes / 2 / 1024**3))


# ----------------------------------------------------------------------------------- command builders


def planetiler_args(
    *, osm: str, output: str, bounds: Sequence[float], maxzoom: int, tmpdir: str
) -> list[str]:
    """Planetiler arguments (OpenMapTiles is its default profile). `--download` fetches the water
    polygons and Natural Earth data that profile needs; `--bounds` limits the output to the region."""
    if not 0 < maxzoom <= 16:
        raise StepError("--maxzoom must be 1..16 (Planetiler's own limit is 16, its default 14)")
    return [
        f"--osm-path={osm}",
        f"--output={output}",
        f"--bounds={bbox_text(bounds)}",
        f"--maxzoom={maxzoom}",
        f"--tmpdir={tmpdir}",
        "--download",
        "--force",
    ]


def planetiler_command(
    runner: str,
    *,
    work: Path,
    osm: Path,
    output: Path,
    bounds: Sequence[float],
    maxzoom: int,
    memory_gb: int,
    image: str = PLANETILER_IMAGE,
    jar: Path | None = None,
) -> tuple[list[str], Path]:
    """(command, working directory). Sources are downloaded under `<work>/data/sources`."""
    if runner == "docker":
        args = planetiler_args(
            osm=f"/data/{osm.name}",
            output=f"/data/{output.name}",
            bounds=bounds,
            maxzoom=maxzoom,
            tmpdir="/data/tmp",
        )
        # The container's own working directory is not documented, so run it in the mounted folder.
        command = [
            "docker", "run", "--rm", "-w", "/data", "-e", f"JAVA_TOOL_OPTIONS=-Xmx{memory_gb}g",
            "-v", f"{work.resolve()}:/data", image, *args,
        ]  # fmt: skip
        return command, work
    args = planetiler_args(
        osm=str(osm), output=str(output), bounds=bounds, maxzoom=maxzoom, tmpdir=str(work / "tmp")
    )
    if runner == "jar":
        if jar is None:
            raise StepError(
                "--runner jar needs --planetiler-jar PATH (Java 25+; see the Planetiler README)"
            )
        return ["java", f"-Xmx{memory_gb}g", "-jar", str(jar), *args], work
    if runner == "binary":
        return ["planetiler", f"--memory={memory_gb}g", *args], work
    raise StepError(f"unknown runner {runner!r}")


def osrm_commands(
    *, directory: Path, image: str = OSRM_IMAGE, name: str = "region"
) -> list[list[str]]:
    """The MLD pipeline from OSRM's README: extract (car profile), partition, customize.

    The extract is copied/linked to `<directory>/<name>.osm.pbf` first so that every output is named
    `<name>.osrm*`, whatever the download was called."""
    run = ["docker", "run", "--rm", "-t", "-v", f"{directory.resolve()}:/data", image]
    base, source = f"/data/{name}.osrm", f"/data/{name}.osm.pbf"
    return [
        [*run, "osrm-extract", "-p", OSRM_PROFILE_IN_IMAGE, source],
        [*run, "osrm-partition", base],
        [*run, "osrm-customize", base],
    ]


def osmium_command(source: Path, output: Path, bbox: Sequence[float]) -> list[str]:
    """`complete_ways` keeps every way that touches the box whole, so roads are not cut mid-segment."""
    return [
        "osmium", "extract", "--bbox", bbox_text(bbox), "--strategy", "complete_ways",
        "--overwrite", "--output", str(output), str(source),
    ]  # fmt: skip


def osrm_routed_hint(directory: Path) -> str:
    return (
        f'docker run --rm -p 127.0.0.1:5000:5000 -v "{directory.resolve()}:/data:ro" {OSRM_IMAGE} '
        "osrm-routed --algorithm mld /data/region.osrm"
    )


# ------------------------------------------------------------------------------------------- helpers


def run(command: Sequence[str], *, cwd: Path | None, dry_run: bool) -> None:
    print("$ " + " ".join(command))
    if dry_run:
        return
    if shutil.which(command[0]) is None:
        raise StepError(
            f"`{command[0]}` is not installed or not on PATH (see docs/maps/HYDERABAD_DATA_RUNBOOK.md)"
        )
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise StepError(f"`{command[0]}` exited with status {completed.returncode}")


def md5_of(path: Path) -> str:
    digest = hashlib.md5(
        usedforsecurity=False
    )  # Geofabrik publishes MD5 only; this is an integrity check
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_md5_file(text: str) -> str:
    """`<32 hex>  <file name>` as written by md5sum."""
    token = text.split()[0].lower() if text.split() else ""
    if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
        raise StepError("the published MD5 file is not in the expected `<hash>  <name>` form")
    return token


def fetch_text(url: str, timeout: float = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "ecomind-map-build/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def download(url: str, target: Path, *, opener: Callable[[str], object] | None = None) -> None:
    """Stream to `<target>.part`, then rename, so an interrupted download never looks complete."""
    if urllib.parse.urlsplit(url).scheme != "https":
        raise StepError("only https downloads are allowed")
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "ecomind-map-build/1"})
    opener = opener or (lambda _u: urllib.request.urlopen(request, timeout=60))
    with opener(url) as response, part.open("wb") as handle:  # type: ignore[attr-defined]
        while block := response.read(CHUNK):
            handle.write(block)
    part.replace(target)


def stage(source: Path, directory: Path, name: str) -> Path:
    """Make `<directory>/<name>.osm.pbf` available without copying gigabytes when a link will do."""
    directory.mkdir(parents=True, exist_ok=True)
    staged = directory / f"{name}.osm.pbf"
    if staged.resolve() == source.resolve():
        return staged
    if staged.exists() or staged.is_symlink():
        staged.unlink()
    try:
        staged.hardlink_to(source)
    except OSError:
        shutil.copy2(source, staged)
    return staged


def write_provenance(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------ validators


def check_mbtiles(path: Path, aoi: Sequence[float]) -> dict[str, object]:
    """Validate a Planetiler (or any OpenMapTiles-schema) MBTiles file; raises StepError on any problem.

    Returns the facts that were checked, for printing and for the provenance record."""
    if not path.is_file():
        raise StepError(f"{path} does not exist")
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            meta = dict(connection.execute("SELECT name, value FROM metadata"))
            tiles = int(connection.execute("SELECT count(*) FROM tiles").fetchone()[0])
            top = connection.execute("SELECT max(zoom_level) FROM tiles").fetchone()[0]
            low = connection.execute("SELECT min(zoom_level) FROM tiles").fetchone()[0]
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise StepError(f"not an MBTiles file ({error})") from error
    if meta.get("format") != "pbf":
        raise StepError(f"format is {meta.get('format')!r}; a vector base map needs format=pbf")
    if tiles == 0:
        raise StepError("the file contains no tiles")
    try:
        layers = {
            item["id"] for item in json.loads(meta.get("json", "{}")).get("vector_layers", [])
        }
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise StepError(f"the `json` metadata row is unreadable ({error})") from error
    missing = OPENMAPTILES_CORE - layers
    if missing:
        raise StepError(f"layers missing for the OpenMapTiles style: {', '.join(sorted(missing))}")
    try:
        west, south, east, north = (float(part) for part in meta["bounds"].split(","))
    except (KeyError, ValueError) as error:
        raise StepError("the `bounds` metadata row is missing or unreadable") from error
    a_west, a_south, a_east, a_north = aoi
    if east < a_west or west > a_east or north < a_south or south > a_north:
        raise StepError(
            f"tile bounds {west},{south},{east},{north} do not overlap the area of interest {bbox_text(aoi)}"
        )
    attribution = meta.get("attribution", "")
    if "openstreetmap" not in attribution.lower():
        raise StepError(
            "the file's attribution does not credit OpenStreetMap; the ODbL requires it"
        )
    return {
        "tiles": tiles,
        "zoom": [low, top],
        "bounds": [west, south, east, north],
        "layers": sorted(layers),
        "attribution": attribution,
    }


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    (lng1, lat1), (lng2, lat2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    )
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def check_route_response(
    body: object, start: tuple[float, float], end: tuple[float, float]
) -> dict[str, float]:
    """Sanity-check an OSRM /route answer. A live road route is never shorter than the straight line."""
    if not isinstance(body, dict) or body.get("code") != "Ok":
        code = body.get("code") if isinstance(body, dict) else None
        raise StepError(f"OSRM did not return a route (code: {code!r})")
    routes = body.get("routes")
    if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
        raise StepError("OSRM answered Ok but returned no route")
    distance_m, duration_s = routes[0].get("distance"), routes[0].get("duration")
    if not isinstance(distance_m, int | float) or not isinstance(duration_s, int | float):
        raise StepError("the route has no numeric distance and duration")
    km, minutes, straight = distance_m / 1000, duration_s / 60, haversine_km(start, end)
    if km < straight * 0.98:
        raise StepError(
            f"route length {km:.1f} km is shorter than the straight line ({straight:.1f} km)"
        )
    if not CHECK_ROUTE_KM[0] <= km <= CHECK_ROUTE_KM[1]:
        raise StepError(
            f"route length {km:.1f} km is outside the plausible {CHECK_ROUTE_KM[0]}-{CHECK_ROUTE_KM[1]} km"
        )
    if not 3 <= minutes <= 240:
        raise StepError(f"travel time {minutes:.0f} min is implausible for {km:.1f} km")
    return {
        "distance_km": round(km, 2),
        "duration_min": round(minutes, 1),
        "straight_line_km": round(straight, 2),
    }


def check_routing(base_url: str, *, fetch: Callable[[str], str] = fetch_text) -> dict[str, float]:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise StepError("--url must be an http(s) URL such as http://127.0.0.1:5000")
    (a, b) = CHECK_ROUTE
    url = f"{base_url.rstrip('/')}/route/v1/driving/{a[0]},{a[1]};{b[0]},{b[1]}?overview=false"
    try:
        body = json.loads(fetch(url))
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise StepError(f"could not get a route from {base_url} ({error})") from error
    return check_route_response(body, a, b)


# ---------------------------------------------------------------------------------------- subcommands


def load_converter():
    spec = importlib.util.spec_from_file_location(
        "mbtiles_to_pmtiles", Path(__file__).with_name("mbtiles_to_pmtiles.py")
    )
    if spec is None or spec.loader is None:  # pragma: no cover - the file is next to this one
        raise StepError("scripts/maps/mbtiles_to_pmtiles.py is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cmd_download(args: argparse.Namespace) -> None:
    url = geofabrik_url(args.region)
    target = args.work_dir / f"{Path(url).name}"
    print(f"source: {url}\ntarget: {target}")
    if args.dry_run:
        print(f"(dry run) would download, then compare with {url}.md5")
        return
    if target.exists() and not args.force:
        raise StepError(f"{target} exists (use --force to download again)")
    published = args.md5
    if not published and not args.skip_md5:
        try:
            published = parse_md5_file(fetch_text(url + ".md5"))
        except (urllib.error.URLError, OSError) as error:
            raise StepError(
                f"could not read the published MD5 ({error}); pass --md5 <hash> from the Geofabrik page, "
                "or --skip-md5 to accept an unverified download"
            ) from error
    download(url, target)
    actual = md5_of(target)
    if published and actual != published.lower():
        target.unlink()
        raise StepError(f"MD5 mismatch (published {published}, got {actual}); the file was deleted")
    print(
        f"downloaded {target.stat().st_size / 1e6:.0f} MB, md5 {actual}"
        + ("" if published else " (NOT verified)")
    )
    write_provenance(
        args.work_dir / "osm-source.json",
        {
            "file": target.name, "url": url, "md5": actual, "md5_verified": bool(published),
            "downloaded_at": now(), "licence": "ODbL 1.0, (c) OpenStreetMap contributors",
        },
    )  # fmt: skip


def cmd_tiles(args: argparse.Namespace) -> None:
    osm = args.input or args.work_dir / f"{Path(geofabrik_url(args.region)).name}"
    if not args.dry_run and not osm.is_file():
        raise StepError(f"{osm} not found: run `download` first or pass --input")
    size = osm.stat().st_size if osm.is_file() else 600 * 1024**2
    memory = args.memory_gb or jvm_memory_gb(size)
    if not args.dry_run:
        args.work_dir.mkdir(parents=True, exist_ok=True)
    output = args.work_dir / "region.mbtiles"
    command, cwd = planetiler_command(
        args.runner, work=args.work_dir, osm=osm, output=output, bounds=args.bbox, maxzoom=args.maxzoom,
        memory_gb=memory, image=args.planetiler_image, jar=args.planetiler_jar,
    )  # fmt: skip
    print(f"planetiler: heap {memory} GB, first run downloads about 1 GB of support data")
    if (
        args.runner == "docker"
        and not args.dry_run
        and osm.parent.resolve() != args.work_dir.resolve()
    ):
        raise StepError(
            "with --runner docker the input must be inside --work-dir (it is the only mounted folder)"
        )
    run(command, cwd=cwd, dry_run=args.dry_run)
    if args.dry_run:
        return
    facts = check_mbtiles(output, aoi_bbox())
    print(f"ok: {facts['tiles']} tiles, zoom {facts['zoom']}, layers {', '.join(facts['layers'])}")  # type: ignore[arg-type]
    write_provenance(
        args.work_dir / "tiles.json",
        {"output": output.name, "built_at": now(), "bounds_requested": list(args.bbox), "runner": args.runner,
         "planetiler_image": args.planetiler_image if args.runner == "docker" else None, "checked": facts},
    )  # fmt: skip


def cmd_check_tiles(args: argparse.Namespace) -> None:
    facts = check_mbtiles(args.path or args.work_dir / "region.mbtiles", aoi_bbox())
    print(json.dumps(facts, indent=2))
    print("ok: this file can be converted with the `pmtiles` step")


def cmd_pmtiles(args: argparse.Namespace) -> None:
    source = args.path or args.work_dir / "region.mbtiles"
    converter_args = [
        str(source),
        "--output",
        str(args.output),
        *(["--force"] if args.force else []),
    ]
    print(
        "$ "
        + " ".join(
            [
                sys.executable,
                str(Path(__file__).with_name("mbtiles_to_pmtiles.py")),
                *converter_args,
            ]
        )
    )
    if args.dry_run:
        return
    check_mbtiles(source, aoi_bbox())  # refuse to convert something the style cannot draw
    if load_converter().main(converter_args) != 0:
        raise StepError("the converter reported an error (see above)")
    print(
        "done: reload the app; it credits OpenStreetMap contributors and any credit the file declares"
    )


def cmd_crop(args: argparse.Namespace) -> None:
    source = args.input or args.work_dir / f"{Path(geofabrik_url(args.region)).name}"
    output = args.work_dir / "region-crop.osm.pbf"
    if not args.dry_run and not source.is_file():
        raise StepError(f"{source} not found: run `download` first or pass --input")
    run(osmium_command(source, output, args.bbox), cwd=None, dry_run=args.dry_run)


def cmd_routing(args: argparse.Namespace) -> None:
    crop = args.work_dir / "region-crop.osm.pbf"
    default = f"{Path(geofabrik_url(args.region)).name}"
    source = args.input or (crop if crop.is_file() else args.work_dir / default)
    if not args.dry_run and not source.is_file():
        raise StepError(
            f"{source} not found: run `download` (and optionally `crop`) first or pass --input"
        )
    directory = args.osrm_dir
    commands = osrm_commands(directory=directory, image=args.osrm_image)
    if not args.dry_run:
        stage(source, directory, "region")
    print(
        "OSRM car profile, MLD pipeline. Memory: a country-sized file needs many GB; crop first for a city."
    )
    for command in commands:
        run(command, cwd=None, dry_run=args.dry_run)
    if args.dry_run:
        return
    finished = directory / "region.osrm.mldgr"
    if not finished.is_file():
        raise StepError(f"{finished} was not produced; osrm-customize did not complete")
    write_provenance(
        directory / "routing.json",
        {"input": source.name, "built_at": now(), "image": args.osrm_image, "profile": "car", "algorithm": "mld",
         "licence": "ODbL 1.0, (c) OpenStreetMap contributors"},
    )  # fmt: skip
    print("ready. Start the server, then verify it:\n  " + osrm_routed_hint(directory))
    print("  python scripts/maps/build_region_data.py check-routing --url http://127.0.0.1:5000")


def cmd_check_routing(args: argparse.Namespace) -> None:
    result = check_routing(args.url)
    print(json.dumps(result, indent=2))
    print("ok: OSRM returned a plausible road route across the region")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--work-dir",
        type=Path,
        default=DEFAULT_WORK,
        help=f"default {DEFAULT_WORK.relative_to(ROOT)}",
    )
    common.add_argument(
        "--region", default=DEFAULT_REGION, help=f"Geofabrik region path, default {DEFAULT_REGION}"
    )
    common.add_argument(
        "--bbox",
        type=parse_bbox,
        default=None,
        help="west,south,east,north (default: the AOI file)",
    )
    common.add_argument(
        "--dry-run", action="store_true", help="print the commands and change nothing"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "download", parents=[common], help="download the Geofabrik extract and verify its MD5"
    )
    p.add_argument("--md5", help="expected MD5 (otherwise read from Geofabrik's .md5 file)")
    p.add_argument(
        "--skip-md5", action="store_true", help="accept an unverified download (recorded as such)"
    )
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser(
        "tiles", parents=[common], help="Planetiler (OpenMapTiles profile) -> region.mbtiles"
    )
    p.add_argument("--input", type=Path, help="an .osm.pbf (default: the downloaded file)")
    p.add_argument("--runner", choices=("docker", "binary", "jar"), default="docker")
    p.add_argument(
        "--planetiler-image",
        default=PLANETILER_IMAGE,
        help="pin a tag or digest for repeatable builds",
    )
    p.add_argument("--planetiler-jar", type=Path)
    p.add_argument(
        "--maxzoom",
        type=int,
        default=14,
        help="default 14 (Planetiler's default; the app over-zooms)",
    )
    p.add_argument("--memory-gb", type=int, help="JVM heap; default about half the .osm.pbf size")
    p.set_defaults(func=cmd_tiles)

    p = sub.add_parser("check-tiles", parents=[common], help="validate a .mbtiles file")
    p.add_argument("path", nargs="?", type=Path)
    p.set_defaults(func=cmd_check_tiles)

    p = sub.add_parser(
        "pmtiles", parents=[common], help="region.mbtiles -> deployment/map-data/region.pmtiles"
    )
    p.add_argument("path", nargs="?", type=Path, help="default: <work-dir>/region.mbtiles")
    p.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PMTILES,
        help=f"default {DEFAULT_PMTILES.relative_to(ROOT)}",
    )
    p.add_argument("--force", action="store_true", help="replace an existing region.pmtiles")
    p.set_defaults(func=cmd_pmtiles)

    p = sub.add_parser(
        "crop", parents=[common], help="optional: osmium extract of the bbox for routing"
    )
    p.add_argument("--input", type=Path)
    p.set_defaults(func=cmd_crop)

    p = sub.add_parser(
        "routing", parents=[common], help="OSRM extract + partition + customize (MLD)"
    )
    p.add_argument(
        "--input", type=Path, help="default: region-crop.osm.pbf if present, else the download"
    )
    p.add_argument(
        "--osrm-image", default=OSRM_IMAGE, help="pin a tag or digest for repeatable builds"
    )
    p.add_argument(
        "--osrm-dir",
        type=Path,
        default=DEFAULT_OSRM_DIR,
        help=f"default {DEFAULT_OSRM_DIR.relative_to(ROOT)}",
    )
    p.set_defaults(func=cmd_routing)

    p = sub.add_parser("check-routing", parents=[common], help="query a running osrm-routed")
    p.add_argument("--url", default="http://127.0.0.1:5000")
    p.set_defaults(func=cmd_check_routing)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.bbox is None:
            args.bbox = aoi_bbox()
        args.func(args)
    except StepError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
