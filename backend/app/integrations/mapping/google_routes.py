"""Google Routes API (``computeRoutes``) adapter.

* Uses the official REST endpoint with an API key sent in ``X-Goog-Api-Key`` (never in the URL, so
  it cannot leak through access logs) and a response field mask that requests only distance,
  duration and the encoded polyline.
* ``routingPreference`` is ``TRAFFIC_UNAWARE``: no live-traffic claim is made and the request stays
  in the lowest billing tier. Durations are therefore free-flow estimates, not ETAs.
* Long routes are split into chunks of at most ``MAX_INTERMEDIATES`` intermediate waypoints
  (10, the largest request that stays in the "Essentials" tier at the time of writing;
  the API hard limit is 25). Chunks share their end points. Nothing is cached or stored: the
  provider's terms restrict storing route results, so each request is a fresh call.
* The HTTP transport is injectable so tests never call the paid API.
"""

from __future__ import annotations

import json
import logging
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence

from pydantic import SecretStr

from app.integrations.mapping.base import (
    LatLng,
    RoadRoute,
    RoadRouteUnavailable,
    UnavailableReason,
)

logger = logging.getLogger(__name__)

ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"
MAX_INTERMEDIATES = 10
_DURATION = re.compile(r"^(\d+)(?:\.\d+)?s$")

# (url, headers, body, timeout_s) -> (status, response_bytes). Raises TimeoutError/OSError.
Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def urllib_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status), bytes(response.read())
    except urllib.error.HTTPError as exc:
        return int(exc.code), bytes(exc.read())


def _waypoint(point: LatLng) -> dict[str, object]:
    return {"location": {"latLng": {"latitude": point.latitude, "longitude": point.longitude}}}


def chunk_points(points: Sequence[LatLng]) -> list[list[LatLng]]:
    """Split a point list into consecutive request segments sharing their end points."""
    size = MAX_INTERMEDIATES + 2
    segments: list[list[LatLng]] = []
    start = 0
    while start < len(points) - 1:
        segments.append(list(points[start : start + size]))
        start += size - 1
    return segments


class GoogleRoutesProvider:
    name = "google_routes"

    def __init__(
        self,
        api_key: SecretStr | None,
        *,
        timeout_seconds: float = 8.0,
        transport: Transport = urllib_transport,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._transport = transport

    @property
    def configured(self) -> bool:
        return self._api_key is not None

    def _unavailable(
        self, reason: UnavailableReason, detail: str | None = None
    ) -> RoadRouteUnavailable:
        return RoadRouteUnavailable(reason=reason, provider=self.name, detail=detail)

    def route(self, points: Sequence[LatLng]) -> RoadRoute | RoadRouteUnavailable:
        if self._api_key is None:
            return self._unavailable("not_configured")
        if len(points) < 2:
            return self._unavailable("too_few_points")
        polylines: list[str] = []
        distance = duration = requests = 0
        for segment in chunk_points(points):
            outcome = self._compute(segment, self._api_key)
            requests += 1
            if isinstance(outcome, RoadRouteUnavailable):
                return outcome
            encoded, metres, seconds = outcome
            polylines.append(encoded)
            distance += metres
            duration += seconds
        return RoadRoute(
            provider=self.name,
            encoded_polylines=tuple(polylines),
            distance_m=distance,
            duration_s=duration,
            traffic_aware=False,
            request_count=requests,
        )

    def _compute(
        self, segment: Sequence[LatLng], api_key: SecretStr
    ) -> tuple[str, int, int] | RoadRouteUnavailable:
        body = {
            "origin": _waypoint(segment[0]),
            "destination": _waypoint(segment[-1]),
            "intermediates": [_waypoint(p) for p in segment[1:-1]],
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_UNAWARE",
            "polylineEncoding": "ENCODED_POLYLINE",
            "units": "METRIC",
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key.get_secret_value(),
            "X-Goog-FieldMask": FIELD_MASK,
        }
        try:
            status, raw = self._transport(
                ENDPOINT, headers, json.dumps(body).encode(), self._timeout
            )
        except TimeoutError:
            logger.warning("google routes request timed out")
            return self._unavailable("timeout")
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                return self._unavailable("timeout")
            logger.warning("google routes network error: %s", type(exc.reason).__name__)
            return self._unavailable("network_error")
        except OSError as exc:
            logger.warning("google routes network error: %s", type(exc).__name__)
            return self._unavailable("network_error")
        if status in (401, 403):
            return self._unavailable("access_denied", f"HTTP {status}")
        if status == 429:
            return self._unavailable("quota_exceeded", "HTTP 429")
        if status != 200:
            return self._unavailable("provider_error", f"HTTP {status}")
        return self._parse(raw)

    def _parse(self, raw: bytes) -> tuple[str, int, int] | RoadRouteUnavailable:
        try:
            payload = json.loads(raw)
        except ValueError:
            return self._unavailable("bad_response", "response is not JSON")
        routes = payload.get("routes") if isinstance(payload, dict) else None
        if not routes:
            return self._unavailable("no_route")
        try:
            route = routes[0]
            encoded = route["polyline"]["encodedPolyline"]
            metres = int(route["distanceMeters"])
            match = _DURATION.match(str(route["duration"]))
            if not isinstance(encoded, str) or not encoded or match is None or metres < 0:
                raise ValueError("unexpected route shape")
            seconds = int(match.group(1))
        except (KeyError, TypeError, ValueError, IndexError):
            return self._unavailable("bad_response", "unexpected route fields")
        return encoded, metres, seconds
