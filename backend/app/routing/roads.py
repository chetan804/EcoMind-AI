"""Road routing adapter: OSRM when configured and reachable, otherwise a
clearly-labelled straight-line estimate with a road-distance factor.

The two outcomes are distinguishable by callers: ``RoadPath.estimated`` is
True when geometry comes from the fallback, and every route records this in
its optimisation metadata (surfaced in the UI).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.gis import haversine_km
from app.core.logging import get_logger

log = get_logger("roads")


@dataclass(slots=True)
class RoadPath:
    geometry: list[list[float]]  # [[lng, lat], ...] GeoJSON order
    distance_km: float
    duration_min: float
    estimated: bool  # True => straight-line fallback, not road geometry
    provider: str


def _polyline_decode(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    index = lat = lng = 0
    factor = 10**precision
    while index < len(encoded):
        for which in (0, 1):
            result = shift = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            d = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += d
            else:
                lng += d
        coords.append((lat / factor, lng / factor))
    return coords


async def route_path(points: list[tuple[float, float]]) -> RoadPath:
    """Geometry for an ordered list of (lat, lng) waypoints (depot + stops + depot)."""
    if not settings.osrm_base_url or len(points) < 2:
        return _fallback(points)
    coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in points)
    url = f"{settings.osrm_base_url}/route/v1/driving/{coords}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"overview": "full", "geometries": "polyline"})
        if resp.status_code != 200:
            raise RuntimeError(f"OSRM HTTP {resp.status_code}")
        data = resp.json()
        route = data["routes"][0]
        decoded = _polyline_decode(route["geometry"])
        geometry = [[lng, lat] for lat, lng in decoded]
        return RoadPath(
            geometry=geometry,
            distance_km=route["distance"] / 1000.0,
            duration_min=route["duration"] / 60.0,
            estimated=False,
            provider="osrm",
        )
    except Exception as e:
        log.warning("osrm_unavailable_fallback", error=str(e)[:200])
        return _fallback(points)


def _fallback(points: list[tuple[float, float]]) -> RoadPath:
    geometry = [[lng, lat] for lat, lng in points]
    distance = sum(
        haversine_km(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])
        for i in range(len(points) - 1)
    )
    road_distance = distance * settings.road_distance_factor
    return RoadPath(
        geometry=geometry,
        distance_km=round(road_distance, 3),
        duration_min=road_distance / 22.0 * 60,  # urban average speed assumption
        estimated=True,
        provider="estimated-straightline",
    )
