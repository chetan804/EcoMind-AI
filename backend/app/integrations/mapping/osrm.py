"""OSRM (Open Source Routing Machine) ``route`` adapter. OPTIONAL and off by default.

OSRM is software you run yourself against an OpenStreetMap extract (see
``docs/maps/ROUTING_PROVIDERS.md``). This adapter only calls the HTTP API of *your* instance,
named by ``OSRM_BASE_URL``. The public demo server is not meant for production use and is not
a default.

* ``GET {base}/route/v1/driving/{lng},{lat};...?overview=full&geometries=polyline`` (precision 5,
  the same encoding as Google's polylines, so the browser draws both the same way).
* One request covers all stops (no 10-waypoint chunking; the server's own limit applies and its
  error is reported as ``provider_error``).
* Durations come from the OSRM profile (free-flow speeds, no live traffic): estimates, not ETAs.
* Nothing is cached or stored. The transport is injectable so tests never open a socket.
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence

from app.integrations.mapping.base import (
    LatLng,
    RoadRoute,
    RoadRouteUnavailable,
    UnavailableReason,
)

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
# OSRM answers HTTP 200 with a "code" for routing outcomes, and 4xx for malformed queries.
_NO_ROUTE_CODES = frozenset({"NoRoute", "NoSegment"})

# (url, timeout_s) -> (status, response_bytes). Raises TimeoutError/OSError.
Transport = Callable[[str, float], tuple[int, bytes]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """An operator-chosen routing server has no reason to redirect; do not follow one."""

    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def urllib_transport(url: str, timeout: float) -> tuple[int, bytes]:
    if not url.startswith(("http://", "https://")):
        raise ValueError("the OSRM base URL must be http(s)")
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")  # noqa: S310
    try:
        with opener.open(request, timeout=timeout) as response:
            return int(response.status), bytes(response.read(MAX_RESPONSE_BYTES + 1))
    except urllib.error.HTTPError as exc:
        return int(exc.code), bytes(exc.read(MAX_RESPONSE_BYTES + 1))


def route_url(base_url: str, points: Sequence[LatLng]) -> str:
    coordinates = ";".join(f"{p.longitude:.6f},{p.latitude:.6f}" for p in points)
    query = "overview=full&geometries=polyline&steps=false&alternatives=false"
    return f"{base_url.rstrip('/')}/route/v1/driving/{coordinates}?{query}"


class OsrmProvider:
    name = "osrm"

    def __init__(
        self,
        base_url: str | None,
        *,
        timeout_seconds: float = 8.0,
        transport: Transport = urllib_transport,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._transport = transport

    @property
    def configured(self) -> bool:
        return self._base_url is not None

    def _unavailable(
        self, reason: UnavailableReason, detail: str | None = None
    ) -> RoadRouteUnavailable:
        return RoadRouteUnavailable(reason=reason, provider=self.name, detail=detail)

    def route(self, points: Sequence[LatLng]) -> RoadRoute | RoadRouteUnavailable:
        if self._base_url is None:
            return self._unavailable("not_configured")
        if len(points) < 2:
            return self._unavailable("too_few_points")
        try:
            status, raw = self._transport(route_url(self._base_url, points), self._timeout)
        except TimeoutError:
            logger.warning("osrm request timed out")
            return self._unavailable("timeout")
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                return self._unavailable("timeout")
            logger.warning("osrm network error: %s", type(exc.reason).__name__)
            return self._unavailable("network_error")
        except OSError as exc:
            logger.warning("osrm network error: %s", type(exc).__name__)
            return self._unavailable("network_error")
        if len(raw) > MAX_RESPONSE_BYTES:
            return self._unavailable("bad_response", "response too large")
        if status in (401, 403):
            return self._unavailable("access_denied", f"HTTP {status}")
        if status == 429:
            return self._unavailable("quota_exceeded", "HTTP 429")
        if status == 400:
            return self._parse(raw, error_status=status)
        if status != 200:
            return self._unavailable("provider_error", f"HTTP {status}")
        return self._parse(raw)

    def _parse(
        self, raw: bytes, *, error_status: int | None = None
    ) -> RoadRoute | RoadRouteUnavailable:
        try:
            payload = json.loads(raw)
        except ValueError:
            return self._unavailable("bad_response", "response is not JSON")
        if not isinstance(payload, dict):
            return self._unavailable("bad_response", "unexpected response shape")
        code = payload.get("code")
        if code in _NO_ROUTE_CODES:
            return self._unavailable("no_route", str(code))
        if error_status is not None or code != "Ok":
            return self._unavailable("provider_error", f"OSRM code {code}")
        try:
            route = payload["routes"][0]
            encoded = route["geometry"]
            metres = round(float(route["distance"]))
            seconds = round(float(route["duration"]))
            if not isinstance(encoded, str) or not encoded or metres < 0 or seconds < 0:
                raise ValueError("unexpected route shape")
        except (KeyError, TypeError, ValueError, IndexError):
            return self._unavailable("bad_response", "unexpected route fields")
        return RoadRoute(
            provider=self.name,
            encoded_polylines=(encoded,),
            distance_m=metres,
            duration_s=seconds,
            traffic_aware=False,
            request_count=1,
        )
