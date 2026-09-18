import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.integrations.routing.base import RouteLeg, RoutingUnavailable


class OSRMAdapter:
    """Small HTTP adapter for OSRM's route service."""

    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def route(self, coordinates: list[tuple[float, float]]) -> list[RouteLeg]:
        if len(coordinates) < 2:
            return []

        coordinate_path = ";".join(
            f"{longitude},{latitude}"
            for latitude, longitude in coordinates
        )
        url = (
            f"{self.base_url}/route/v1/driving/{quote(coordinate_path, safe=';,.-')}"
            "?overview=false&steps=false"
        )
        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise RoutingUnavailable("OSRM routing is unavailable") from exc

        if payload.get("code") != "Ok":
            raise RoutingUnavailable("OSRM returned an unsuccessful route response")

        routes = payload.get("routes") or []
        if not routes:
            raise RoutingUnavailable("OSRM returned no route")

        route = routes[0]
        legs = route.get("legs") or []
        return [
            RouteLeg(
                distance_km=float(leg.get("distance", 0)) / 1000,
                duration_minutes=float(leg.get("duration", 0)) / 60,
            )
            for leg in legs
        ]
