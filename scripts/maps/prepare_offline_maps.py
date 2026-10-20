#!/usr/bin/env python3
"""Prepare the data for the built-in offline map (no API key, no run-time third party).

Two operator steps, both optional and both run once per region, not by the app:

  assets   Copy more font ranges (for example Devanagari or Telugu place names) from the
           protomaps/basemaps-assets repository into frontend/public/map-assets. The repository
           already ships the Latin ranges.
  tiles    Cut a regional vector-tile file (PMTiles, OpenStreetMap data) out of a Protomaps planet build
           with the `pmtiles` command line tool and write it to deployment/map-data/region.pmtiles.

Examples
  python scripts/maps/prepare_offline_maps.py assets --all-ranges
  python scripts/maps/prepare_offline_maps.py tiles --bbox 78.2,17.2,78.7,17.6 \
      --source https://build.protomaps.com/20261001.pmtiles --maxzoom 15

The tile step needs the `pmtiles` CLI (https://github.com/protomaps/go-pmtiles/releases) and network
access to the source. Map data is (c) OpenStreetMap contributors under the ODbL; the app shows that
attribution on every map. Use --dry-run to print the command without running it.
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS_ZIP = "https://codeload.github.com/protomaps/basemaps-assets/zip/refs/heads/main"
FONTS = ("Noto Sans Regular", "Noto Sans Medium", "Noto Sans Italic")
DEFAULT_RANGES = ("0-255", "256-511", "8192-8447")
DEFAULT_OUTPUT = ROOT / "deployment" / "map-data" / "region.pmtiles"
DEFAULT_ASSETS = ROOT / "frontend" / "public" / "map-assets"
MAX_ZOOM_LIMIT = 15  # protomaps basemaps are built to z15; higher values only over-zoom


class UsageError(ValueError):
    """The arguments are not usable (reported without a traceback)."""


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    """`west,south,east,north` in degrees. Rejects anything that cannot be a real box."""
    try:
        west, south, east, north = (float(part) for part in value.split(","))
    except ValueError as error:
        raise UsageError("--bbox needs four numbers: west,south,east,north") from error
    if not (-180 <= west < east <= 180):
        raise UsageError("--bbox: west must be below east, both within -180..180")
    if not (-90 <= south < north <= 90):
        raise UsageError("--bbox: south must be below north, both within -90..90")
    return west, south, east, north


def extract_command(
    pmtiles_bin: str, source: str, output: Path, bbox: tuple[float, float, float, float], maxzoom: int
) -> list[str]:
    if not 0 <= maxzoom <= MAX_ZOOM_LIMIT:
        raise UsageError(f"--maxzoom must be between 0 and {MAX_ZOOM_LIMIT}")
    box = ",".join(f"{v:g}" for v in bbox)
    return [pmtiles_bin, "extract", source, str(output), f"--bbox={box}", f"--maxzoom={maxzoom}"]


def run_tiles(args: argparse.Namespace) -> int:
    command = extract_command(
        args.pmtiles_bin, args.source, Path(args.output), parse_bbox(args.bbox), args.maxzoom
    )
    print(" ".join(command))
    if args.dry_run:
        return 0
    if shutil.which(args.pmtiles_bin) is None:
        raise UsageError(
            f"`{args.pmtiles_bin}` not found. Install the go-pmtiles CLI: "
            "https://github.com/protomaps/go-pmtiles/releases"
        )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, check=False)
    if result.returncode == 0:
        print(f"Wrote {args.output}. Restart or reload the frontend; no rebuild is needed.")
    return result.returncode


def wanted_member(name: str, all_ranges: bool) -> str | None:
    """Destination (relative to map-assets) of a zip member, or None when it is not wanted."""
    parts = name.split("/", 1)
    if len(parts) != 2:
        return None
    rel = parts[1]
    pieces = rel.split("/")
    is_font_file = (
        len(pieces) == 3 and pieces[0] == "fonts" and pieces[1] in FONTS and pieces[2].endswith(".pbf")
    )
    if is_font_file and (all_ranges or pieces[2][:-4] in DEFAULT_RANGES):
        return rel
    return None


def run_assets(args: argparse.Namespace) -> int:
    print(f"Downloading {ASSETS_ZIP}")
    with urllib.request.urlopen(ASSETS_ZIP, timeout=120) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    destination = Path(args.dest)
    copied = 0
    for member in archive.namelist():
        rel = wanted_member(member, args.all_ranges)
        if rel is None:
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(member))
        copied += 1
    print(f"Copied {copied} glyph files into {destination}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    assets = sub.add_parser("assets", help="copy font glyph ranges into frontend/public/map-assets")
    assets.add_argument("--all-ranges", action="store_true", help="copy every glyph range (about 12 MB)")
    assets.add_argument("--dest", default=str(DEFAULT_ASSETS))
    assets.set_defaults(func=run_assets)
    tiles = sub.add_parser("tiles", help="cut a regional PMTiles file out of a Protomaps build")
    tiles.add_argument("--bbox", required=True, help="west,south,east,north in degrees")
    tiles.add_argument("--source", required=True, help="Protomaps build URL or local .pmtiles file")
    tiles.add_argument("--output", default=str(DEFAULT_OUTPUT))
    tiles.add_argument("--maxzoom", type=int, default=15)
    tiles.add_argument("--pmtiles-bin", default="pmtiles")
    tiles.add_argument("--dry-run", action="store_true")
    tiles.set_defaults(func=run_tiles)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except UsageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
