#!/usr/bin/env python3
"""Write a tiny SYNTHETIC vector-tile file (PMTiles) so the offline map pipeline can be exercised
without real map data: tile protocol, style, fonts, sprites, markers and routes in a real browser.

The features are invented geometry (a lake, a park, a road grid, three place names) using the
Protomaps layer schema. They are NOT a map of anywhere and must never ship as a basemap or be shown
as one. Developer tooling only (not run in CI):

    python -m venv /tmp/v && /tmp/v/bin/pip install pmtiles mapbox-vector-tile
    /tmp/v/bin/python tests/e2e/visual/make-synthetic-tiles.py /tmp/synthetic.pmtiles
"""

from __future__ import annotations

import gzip
import math
import sys
from pathlib import Path

import mapbox_vector_tile
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from shapely.geometry import LineString, Point, box
from shapely.ops import transform

WEST, SOUTH, EAST, NORTH = 78.30, 17.30, 78.60, 17.55
MIN_ZOOM, MAX_ZOOM = 8, 15
R = 6378137.0


def merc(lon: float, lat: float) -> tuple[float, float]:
    return (R * math.radians(lon), R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def to_merc(geom):
    return transform(lambda x, y, z=None: merc(x, y), geom)


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    size = 2 * math.pi * R / 2**z
    origin = -math.pi * R
    return (origin + x * size, math.pi * R - (y + 1) * size, origin + (x + 1) * size, math.pi * R - y * size)


def tile_xy(z: int, lon: float, lat: float) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def world_features():
    lake = box(78.43, 17.40, 78.47, 17.43)
    park = box(78.36, 17.46, 78.40, 17.50)
    roads = []
    lon = WEST
    while lon <= EAST:
        roads.append((LineString([(lon, SOUTH), (lon, NORTH)]), "major_road" if round(lon * 100) % 4 == 0 else "minor_road"))
        lon += 0.01
    lat = SOUTH
    while lat <= NORTH:
        roads.append((LineString([(WEST, lat), (EAST, lat)]), "major_road" if round(lat * 100) % 4 == 0 else "minor_road"))
        lat += 0.01
    roads.append((LineString([(WEST, 17.33), (EAST, 17.52)]), "highway"))
    places = [("Synthetic Town A", 78.41, 17.45), ("Synthetic Town B", 78.52, 17.38), ("Synthetic Town C", 78.34, 17.34)]
    return lake, park, roads, places


def build_tile(z: int, x: int, y: int) -> bytes:
    minx, miny, maxx, maxy = tile_bounds(z, x, y)
    clip = box(minx, miny, maxx, maxy)
    lake, park, roads, places = world_features()
    layers = [{"name": "earth", "features": [{"geometry": clip.wkt, "properties": {"kind": "earth"}}]}]
    water = to_merc(lake).intersection(clip)
    if not water.is_empty:
        layers.append({"name": "water", "features": [{"geometry": water.wkt, "properties": {"kind": "lake"}}]})
    land = to_merc(park).intersection(clip)
    if not land.is_empty:
        layers.append({"name": "landuse", "features": [{"geometry": land.wkt, "properties": {"kind": "park"}}]})
    road_features = []
    for line, kind in roads:
        if kind == "minor_road" and z < 13:
            continue
        piece = to_merc(line).intersection(clip)
        if piece.is_empty:
            continue
        detail = {"highway": "motorway", "major_road": "primary", "minor_road": "residential"}[kind]
        road_features.append({"geometry": piece.wkt, "properties": {"kind": kind, "kind_detail": detail, "level": 0, "sort_rank": 10, "min_zoom": 8}})
    if road_features:
        layers.append({"name": "roads", "features": road_features})
    place_features = []
    for name, lon, lat in places:
        p = Point(*merc(lon, lat))
        if clip.contains(p):
            place_features.append({"geometry": p.wkt, "properties": {"kind": "locality", "name": name, "name:en": name, "population_rank": 9, "min_zoom": 8, "pmap:min_zoom": 8, "sort_rank": 10}})
    if place_features:
        layers.append({"name": "places", "features": place_features})
    data = mapbox_vector_tile.encode(layers, default_options={"quantize_bounds": (minx, miny, maxx, maxy), "extents": 4096})
    return gzip.compress(data)


def main(out: Path) -> None:
    tiles = {}
    for z in range(MIN_ZOOM, MAX_ZOOM + 1):
        x0, y1 = tile_xy(z, WEST, SOUTH)
        x1, y0 = tile_xy(z, EAST, NORTH)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                tiles[zxy_to_tileid(z, x, y)] = build_tile(z, x, y)
    with write(str(out)) as writer:
        for tile_id in sorted(tiles):
            writer.write_tile(tile_id, tiles[tile_id])
        writer.finalize(
            {
                "tile_type": TileType.MVT,
                "tile_compression": Compression.GZIP,
                "min_zoom": MIN_ZOOM,
                "max_zoom": MAX_ZOOM,
                "min_lon_e7": int(WEST * 1e7),
                "min_lat_e7": int(SOUTH * 1e7),
                "max_lon_e7": int(EAST * 1e7),
                "max_lat_e7": int(NORTH * 1e7),
                "center_zoom": 12,
                "center_lon_e7": int((WEST + EAST) / 2 * 1e7),
                "center_lat_e7": int((SOUTH + NORTH) / 2 * 1e7),
            },
            {"name": "SYNTHETIC test tiles (not a map)", "vector_layers": [{"id": n} for n in ("earth", "water", "landuse", "roads", "places")]},
        )
    print(f"{len(tiles)} tiles, {out.stat().st_size} bytes -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "synthetic.pmtiles"))
