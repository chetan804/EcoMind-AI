#!/usr/bin/env python3
"""Convert a vector-tile MBTiles file (for example a MapTiler regional OpenStreetMap dataset) to the
PMTiles file the app serves, and check the result.

  pip install --require-hashes -r scripts/maps/requirements.lock
  python scripts/maps/mbtiles_to_pmtiles.py hyderabad.mbtiles            # -> deployment/map-data/region.pmtiles
  python scripts/maps/mbtiles_to_pmtiles.py hyderabad.mbtiles --output /tmp/hyd.pmtiles --maxzoom 14

What it does beyond the library's own converter: it expands the MBTiles `json` metadata row (which
holds `vector_layers`) into the PMTiles metadata, because the app reads `vector_layers` to decide
which map style fits the file (Protomaps or OpenMapTiles), and it reads the result back to verify it.

Licensing: the data is NOT ours to redistribute. Download it under your own account and accept its
terms (MapTiler's free on-prem tier is for evaluation and non-commercial use; see
docs/maps/OFFLINE_MAPS.md). The output is git-ignored; never commit it. The app shows the credit the
file requires ("© MapTiler © OpenStreetMap contributors" for MapTiler data).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "deployment" / "map-data" / "region.pmtiles"
OPENMAPTILES_CORE = {"transportation", "place", "water"}
# Metadata keys worth keeping; `tilestats` (per-attribute statistics) can be megabytes and is unused.
KEEP = ("name", "description", "version", "attribution", "type", "format", "bounds", "center", "minzoom", "maxzoom")


class ConversionError(ValueError):
    """The input cannot be converted (reported without a traceback)."""


def read_metadata(connection: sqlite3.Connection) -> dict[str, object]:
    """MBTiles metadata with the `json` row expanded; raises ConversionError if unusable."""
    try:
        rows = dict(connection.execute("SELECT name, value FROM metadata"))
        connection.execute("SELECT 1 FROM tiles LIMIT 1").fetchone()
    except sqlite3.DatabaseError as error:
        raise ConversionError(f"not an MBTiles file ({error})") from error
    if rows.get("format") != "pbf":
        raise ConversionError(
            f"format is {rows.get('format')!r}; only vector tiles (format=pbf) can be used as a base map"
        )
    for key in ("minzoom", "maxzoom"):
        if key not in rows:
            raise ConversionError(f"metadata has no {key}")
    metadata: dict[str, object] = {key: rows[key] for key in KEEP if key in rows}
    extra = rows.get("json")
    if extra:
        try:
            parsed = json.loads(extra)
        except json.JSONDecodeError as error:
            raise ConversionError(f"metadata `json` row is not valid JSON ({error})") from error
        if isinstance(parsed, dict):
            metadata.update({k: v for k, v in parsed.items() if k != "tilestats"})
    return metadata


def layer_ids(metadata: dict[str, object]) -> list[str]:
    layers = metadata.get("vector_layers")
    if not isinstance(layers, list):
        return []
    return [str(layer["id"]) for layer in layers if isinstance(layer, dict) and "id" in layer]


def schema_of(metadata: dict[str, object]) -> str:
    ids = set(layer_ids(metadata))
    if OPENMAPTILES_CORE <= ids:
        return "openmaptiles"
    if {"earth", "roads"} <= ids:
        return "protomaps"
    return "unknown"


def convert(source: Path, output: Path, maxzoom: int | None) -> dict[str, object]:
    from pmtiles.convert import mbtiles_to_header_json
    from pmtiles.tile import Compression, tileid_to_zxy, zxy_to_tileid
    from pmtiles.writer import write

    connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        metadata = read_metadata(connection)
        top = int(maxzoom if maxzoom is not None else str(metadata["maxzoom"]))
        ids = sorted(
            zxy_to_tileid(z, x, (1 << z) - 1 - y)
            for z, x, y in connection.execute(
                "SELECT zoom_level, tile_column, tile_row FROM tiles WHERE zoom_level <= ?", (top,)
            )
        )
        if not ids:
            raise ConversionError("the file has no tiles (at or below --maxzoom)")
        output.parent.mkdir(parents=True, exist_ok=True)
        flat = {k: str(v) for k, v in metadata.items() if k in ("minzoom", "maxzoom", "bounds", "center", "format")}
        header, _ = mbtiles_to_header_json({**flat, "maxzoom": str(top), "format": "pbf"})
        header["tile_compression"] = Compression.GZIP
        temporary = output.with_suffix(output.suffix + ".part")
        with write(str(temporary)) as writer:
            for tile_id in ids:
                z, x, y = tileid_to_zxy(tile_id)
                row = connection.execute(
                    "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                    (z, x, (1 << z) - 1 - y),
                ).fetchone()
                data = bytes(row[0])
                writer.write_tile(tile_id, data if data[:2] == b"\x1f\x8b" else gzip.compress(data, mtime=0))
            metadata["maxzoom"] = str(top)
            writer.finalize(header, metadata)
        temporary.replace(output)
    finally:
        connection.close()
    return metadata


def verify(output: Path) -> tuple[int, dict[str, object]]:
    """Read the file back with the library's reader; returns (tile count, metadata)."""
    from pmtiles.reader import MmapSource, Reader, all_tiles
    from pmtiles.tile import TileType

    with output.open("rb") as handle:
        source = MmapSource(handle)
        reader = Reader(source)
        header = reader.header()
        metadata = reader.metadata()
        count = sum(1 for _ in all_tiles(source))
    if header["tile_type"] != TileType.MVT:
        raise ConversionError("the result is not a vector-tile PMTiles file")
    return count, metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="vector-tile .mbtiles file")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"default {DEFAULT_OUTPUT.relative_to(ROOT)}")
    parser.add_argument("--maxzoom", type=int, help="drop tiles above this zoom (the app over-zooms)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing output file")
    args = parser.parse_args(argv)
    try:
        if not args.source.is_file():
            raise ConversionError(f"{args.source} does not exist")
        if args.output.exists() and not args.force:
            raise ConversionError(f"{args.output} exists (use --force to replace it)")
        metadata = convert(args.source, args.output, args.maxzoom)
        count, written = verify(args.output)
    except ConversionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    schema = schema_of(written)
    size = args.output.stat().st_size / 1_000_000
    print(f"wrote {args.output} ({size:.1f} MB, {count} tiles, zoom {written.get('minzoom')}-{written.get('maxzoom')})")
    print(f"layers: {', '.join(layer_ids(written)) or '(none declared)'}")
    print(f"detected layout: {schema}; attribution in file: {metadata.get('attribution', '(none)')}")
    if schema == "unknown":
        print("warning: neither the Protomaps nor the OpenMapTiles layout was found; the app will say so", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
