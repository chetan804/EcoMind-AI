#!/usr/bin/env python3
"""Write a SYNTHETIC OpenMapTiles-schema MBTiles file, to test the map pipeline without real data.

  pip install mapbox-vector-tile shapely
  python scripts/maps/make_openmaptiles_fixture.py /tmp/synthetic.mbtiles
  python scripts/maps/mbtiles_to_pmtiles.py /tmp/synthetic.mbtiles --output deployment/map-data/region.pmtiles

Everything drawn is INVENTED (an artificial lake, park, street grid, ring road and "Test ..." place
names placed over the Hyderabad area). It is NOT OpenStreetMap or MapTiler data, carries no real
street or place, and must never be shown to users as a map of the city. It exists only so the
converter, the OpenMapTiles style and the map screens can be exercised end to end before the real
dataset has been downloaded. The metadata says so (name and description).
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path

import mapbox_vector_tile
from shapely.geometry import LineString, Polygon, box
from shapely.ops import transform

BOUNDS = (78.2, 17.2, 78.65, 17.6)
MAXZOOM = 14
EXTENT = 4096
LON0, LAT0 = 78.40, 17.40  # centre of the invented scene

LAYERS = ["landcover", "landuse", "park", "water", "waterway", "building", "transportation", "transportation_name", "boundary", "water_name", "place"]


def lonlat_to_world(lon: float, lat: float) -> tuple[float, float]:
    """Web-Mercator in 0..1 (y down)."""
    x = (lon + 180) / 360
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2
    return x, y


def poly(*coords: tuple[float, float]) -> Polygon:
    return Polygon([lonlat_to_world(lon, lat) for lon, lat in coords])


def line(*coords: tuple[float, float]) -> LineString:
    return LineString([lonlat_to_world(lon, lat) for lon, lat in coords])


def scene() -> dict[str, list[tuple[object, dict[str, object]]]]:
    layers: dict[str, list[tuple[object, dict[str, object]]]] = {name: [] for name in LAYERS}
    d = 0.01
    layers["landcover"].append((poly((78.2, 17.2), (78.35, 17.2), (78.35, 17.3), (78.2, 17.3)), {"class": "grass"}))
    layers["landcover"].append((poly((78.5, 17.45), (78.65, 17.45), (78.65, 17.6), (78.5, 17.6)), {"class": "wood"}))
    layers["landuse"].append((poly((78.45, 17.3), (78.55, 17.3), (78.55, 17.37), (78.45, 17.37)), {"class": "industrial"}))
    layers["landuse"].append((poly((78.36, 17.42), (78.38, 17.42), (78.38, 17.44), (78.36, 17.44)), {"class": "hospital"}))
    layers["park"].append((poly((78.40, 17.36), (78.43, 17.36), (78.43, 17.39), (78.40, 17.39)), {"class": "park", "name": "Test Park"}))
    layers["water"].append((poly((78.30, 17.45), (78.36, 17.45), (78.37, 17.5), (78.31, 17.52), (78.28, 17.48)), {"class": "lake", "name": "Test Lake"}))
    layers["waterway"].append((line((78.2, 17.52), (78.28, 17.48), (78.2, 17.43)), {"class": "river"}))
    layers["water_name"].append((line((78.33, 17.485), (78.33, 17.486)).centroid, {"class": "lake", "name": "Test Lake"}))
    for i in range(0, 41):  # invented street grid, 0.01 degree spacing
        lon = 78.30 + i * d / 2
        lat = 17.30 + i * d / 2
        kind = "tertiary" if i % 5 == 0 else "minor"
        layers["transportation"].append((line((lon, 17.30), (lon, 17.50)), {"class": kind}))
        layers["transportation"].append((line((78.30, lat), (78.50, lat)), {"class": kind}))
    for k in range(3, 38, 6):  # building footprints inside the grid
        for j in range(3, 38, 5):
            lon, lat = 78.30 + k * d / 2 + 0.0008, 17.30 + j * d / 2 + 0.0008
            layers["building"].append((poly((lon, lat), (lon + 0.0014, lat), (lon + 0.0014, lat + 0.0014), (lon, lat + 0.0014)), {}))
    ring = [(78.28 + 0.25 * math.cos(a / 20 * math.pi), 17.40 + 0.17 * math.sin(a / 20 * math.pi)) for a in range(40)]
    layers["transportation"].append((line(*ring, ring[0]), {"class": "motorway"}))
    layers["transportation"].append((line((78.2, 17.4), (78.65, 17.38)), {"class": "primary"}))
    layers["transportation"].append((line((78.4, 17.2), (78.41, 17.6)), {"class": "secondary"}))
    layers["transportation"].append((line((78.2, 17.25), (78.65, 17.3)), {"class": "rail"}))
    layers["transportation_name"].append((line((78.2, 17.4), (78.65, 17.38)), {"class": "primary", "name": "Test Main Road"}))
    layers["boundary"].append((line((78.2, 17.55), (78.65, 17.5)), {"admin_level": 4, "maritime": 0}))
    for lon, lat, cls, name in [
        (78.40, 17.40, "city", "Test City"), (78.33, 17.34, "suburb", "Test Heights"),
        (78.48, 17.43, "suburb", "Test Park Colony"), (78.55, 17.33, "town", "Example Town"),
        (78.23, 17.55, "village", "Sample Village"),
    ]:  # fmt: skip
        layers["place"].append((poly((lon, lat), (lon, lat), (lon, lat)).centroid, {"class": cls, "name": name, "name:en": name, "rank": 1}))
    return layers


def encode_tile(layers, z: int, x: int, y: int) -> bytes | None:
    n = 1 << z
    tile_box = box(x / n, y / n, (x + 1) / n, (y + 1) / n)
    margin = tile_box.buffer(8 / EXTENT / n)

    def to_tile(wx: float, wy: float, *_: float) -> tuple[float, float]:
        return (wx * n - x) * EXTENT, (1 - (wy * n - y)) * EXTENT  # MVT y axis is up in encode()

    out = []
    for name, features in layers.items():
        kept = []
        for geometry, props in features:
            if name == "building" and z < 14:
                continue
            if not geometry.intersects(margin):
                continue
            clipped = geometry.intersection(margin)
            if clipped.is_empty:
                continue
            kept.append({"geometry": transform(to_tile, clipped), "properties": props})
        if kept:
            out.append({"name": name, "features": kept})
    if not out:
        return None
    return mapbox_vector_tile.encode(out, default_options={"extents": EXTENT, "y_coord_down": False})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        print(f"error: {args.output} exists", file=sys.stderr)
        return 1
    layers = scene()
    connection = sqlite3.connect(args.output)
    connection.executescript(
        "CREATE TABLE metadata (name TEXT, value TEXT);"
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);"
        "CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row);"
    )
    vector_layers = [{"id": name, "fields": {}, "minzoom": 0, "maxzoom": MAXZOOM} for name in LAYERS]
    metadata = {
        "name": "SYNTHETIC test fixture (not real map data)",
        "description": "Invented geometry in the OpenMapTiles layout, for software tests only.",
        "version": "1", "type": "baselayer", "format": "pbf",
        "bounds": ",".join(map(str, BOUNDS)), "center": f"{LON0},{LAT0},10",
        "minzoom": "0", "maxzoom": str(MAXZOOM),
        "attribution": "Synthetic test data",
        "json": json.dumps({"vector_layers": vector_layers}),
    }  # fmt: skip
    connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
    count = 0
    for z in range(MAXZOOM + 1):
        n = 1 << z
        x0, y0 = lonlat_to_world(BOUNDS[0], BOUNDS[3])
        x1, y1 = lonlat_to_world(BOUNDS[2], BOUNDS[1])
        for x in range(int(x0 * n), int(x1 * n) + 1):
            for y in range(int(y0 * n), int(y1 * n) + 1):
                data = encode_tile(layers, z, x, y)
                if data:
                    connection.execute("INSERT INTO tiles VALUES (?,?,?,?)", (z, x, n - 1 - y, data))
                    count += 1
    connection.commit()
    connection.close()
    print(f"wrote {args.output}: {count} tiles, zoom 0-{MAXZOOM}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
