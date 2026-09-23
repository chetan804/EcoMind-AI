"""Portable geospatial helpers.

Spatial strategy (docs/adr/0002-spatial-strategy.md):
- Points are stored as indexed ``latitude``/``longitude`` doubles.
- Service-area boundaries are validated GeoJSON polygons (JSONB).
- Exact geometry uses Shapely; distance uses haversine.
- PostGIS is the documented production upgrade path for heavy spatial
  workloads; every spatial operation funnels through this module so the swap
  is localised.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Point, Polygon, shape
from shapely.geometry.base import BaseGeometry

EARTH_RADIUS_M = 6_371_008.8
MIN_LAT, MAX_LAT = -90.0, 90.0
MIN_LNG, MAX_LNG = -180.0, 180.0


class GeoValidationError(ValueError):
    pass


def validate_latitude(v: float) -> float:
    if v is None or not (MIN_LAT <= v <= MAX_LAT):
        raise GeoValidationError(f"Latitude must be within [{MIN_LAT}, {MAX_LAT}].")
    return v


def validate_longitude(v: float) -> float:
    if v is None or not (MIN_LNG <= v <= MAX_LNG):
        raise GeoValidationError(f"Longitude must be within [{MIN_LNG}, {MAX_LNG}].")
    return v


@dataclass(slots=True)
class BBox:
    min_lat: float
    min_lng: float
    max_lat: float
    max_lng: float

    def contains(self, lat: float, lng: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lng <= lng <= self.max_lng


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return haversine_m(lat1, lng1, lat2, lng2) / 1000.0


def parse_polygon_geojson(geojson: dict[str, Any]) -> Polygon:
    """Validate a GeoJSON Polygon dict, returning a Shapely polygon."""
    try:
        geom: BaseGeometry = shape(geojson)
    except Exception as e:
        raise GeoValidationError("Boundary must be valid GeoJSON geometry.") from e
    if not isinstance(geom, Polygon):
        raise GeoValidationError("Boundary must be a GeoJSON Polygon.")
    if not geom.is_valid:
        geom = geom.buffer(0)
        if not geom.is_valid or geom.is_empty:
            raise GeoValidationError("Polygon geometry is invalid (self-intersecting or empty).")
    if geom.area == 0:
        raise GeoValidationError("Polygon has zero area.")
    return geom


def polygon_centroid(polygon: Polygon) -> tuple[float, float]:
    c = polygon.centroid
    return c.y, c.x  # lat, lng


def polygon_bbox(polygon: Polygon) -> BBox:
    minx, miny, maxx, maxy = polygon.bounds
    return BBox(min_lat=miny, min_lng=minx, max_lat=maxy, max_lng=maxx)


def point_in_polygon(lat: float, lng: float, polygon: Polygon) -> bool:
    return polygon.contains(Point(lng, lat))
