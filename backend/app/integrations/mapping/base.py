"""Road-routing provider boundary.

A provider turns an ordered list of points into a road route (geometry, distance, duration).
The application never invents road geometry: when no provider is configured, or a call fails,
the result says so (``RoadRouteUnavailable``) and the UI draws a clearly labelled straight-line
fallback instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

UnavailableReason = Literal[
    "not_configured",  # no server API key
    "too_few_points",
    "provider_error",  # the provider answered with an error status
    "quota_exceeded",  # 429 / RESOURCE_EXHAUSTED
    "access_denied",  # 401/403: key invalid, API not enabled or key restricted
    "timeout",
    "network_error",
    "no_route",  # the provider found no drivable route between the points
    "bad_response",
]


@dataclass(frozen=True)
class LatLng:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class RoadRoute:
    """A route computed by a routing provider. ``encoded_polylines`` use Google's encoding."""

    provider: str
    encoded_polylines: tuple[str, ...]
    distance_m: int
    duration_s: int
    traffic_aware: bool
    request_count: int


@dataclass(frozen=True)
class RoadRouteUnavailable:
    reason: UnavailableReason
    provider: str
    detail: str | None = None


class RoadRouteProvider(Protocol):
    name: str

    def route(self, points: Sequence[LatLng]) -> RoadRoute | RoadRouteUnavailable:
        """Drive through ``points`` in the given order (first = origin, last = destination)."""
        ...
