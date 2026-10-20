"""OSRM adapter and provider selection against a mocked transport (no network)."""

from __future__ import annotations

import json
import urllib.error
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.integrations.mapping.base import LatLng, RoadRoute, RoadRouteUnavailable
from app.integrations.mapping.factory import build_road_route_provider
from app.integrations.mapping.google_routes import GoogleRoutesProvider
from app.integrations.mapping.osrm import MAX_RESPONSE_BYTES, OsrmProvider, route_url

BASE = "http://osrm.internal:5000"
A, B, C = LatLng(17.40, 78.46), LatLng(17.41, 78.47), LatLng(17.42, 78.48)


def ok(
    distance: float = 1234.6, duration: float = 301.2, geometry: str = "_p~iF~ps|U_ulLnnqC"
) -> bytes:
    return json.dumps(
        {
            "code": "Ok",
            "routes": [{"distance": distance, "duration": duration, "geometry": geometry}],
            "waypoints": [],
        }
    ).encode()


class Recorder:
    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, float]] = []

    def __call__(self, url: str, timeout: float) -> tuple[int, bytes]:
        self.calls.append((url, timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return (int(response[0]), bytes(response[1]))


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "environment": "test",
        "secret_key": "x" * 40,
        "database_url": "postgresql+psycopg://u:p@localhost/db",
    }
    return Settings(_env_file=None, **{**base, **overrides})


def test_route_url_uses_lng_lat_order_and_full_polyline() -> None:
    url = route_url(BASE + "/", [A, B, C])
    parts = urlsplit(url)
    assert (
        parts.path
        == "/route/v1/driving/78.460000,17.400000;78.470000,17.410000;78.480000,17.420000"
    )
    query = parse_qs(parts.query)
    assert query["overview"] == ["full"] and query["geometries"] == ["polyline"]
    assert query["steps"] == ["false"] and query["alternatives"] == ["false"]


def test_success_returns_one_request_route_without_traffic_claim() -> None:
    transport = Recorder((200, ok()))
    result = OsrmProvider(BASE, timeout_seconds=3, transport=transport).route([A, B, C])
    assert result == RoadRoute(
        provider="osrm",
        encoded_polylines=("_p~iF~ps|U_ulLnnqC",),
        distance_m=1235,
        duration_s=301,
        traffic_aware=False,
        request_count=1,
    )
    assert len(transport.calls) == 1 and transport.calls[0][1] == 3


def test_not_configured_and_too_few_points_make_no_request() -> None:
    transport = Recorder()
    assert OsrmProvider(None, transport=transport).route([A, B]) == RoadRouteUnavailable(
        reason="not_configured", provider="osrm"
    )
    assert OsrmProvider(BASE, transport=transport).route([A]) == RoadRouteUnavailable(
        reason="too_few_points", provider="osrm"
    )
    assert transport.calls == []


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        ((200, json.dumps({"code": "NoRoute", "message": "x"}).encode()), "no_route"),
        ((200, json.dumps({"code": "NoSegment"}).encode()), "no_route"),
        ((400, json.dumps({"code": "InvalidQuery"}).encode()), "provider_error"),
        ((200, json.dumps({"code": "TooBig"}).encode()), "provider_error"),
        ((403, b""), "access_denied"),
        ((429, b""), "quota_exceeded"),
        ((500, b"oops"), "provider_error"),
        ((200, b"<html>"), "bad_response"),
        ((200, b"[]"), "bad_response"),
        ((200, json.dumps({"code": "Ok", "routes": []}).encode()), "bad_response"),
        (
            (
                200,
                json.dumps(
                    {"code": "Ok", "routes": [{"distance": -1, "duration": 1, "geometry": "a"}]}
                ).encode(),
            ),
            "bad_response",
        ),
        (
            (
                200,
                json.dumps(
                    {"code": "Ok", "routes": [{"distance": 1, "duration": 1, "geometry": ""}]}
                ).encode(),
            ),
            "bad_response",
        ),
        ((200, b" " * (MAX_RESPONSE_BYTES + 1)), "bad_response"),
        (TimeoutError(), "timeout"),
        (urllib.error.URLError(TimeoutError()), "timeout"),
        (urllib.error.URLError(ConnectionRefusedError()), "network_error"),
        (ConnectionResetError(), "network_error"),
    ],
)
def test_failures_are_reported_with_a_reason_never_raised(response: Any, reason: str) -> None:
    result = OsrmProvider(BASE, transport=Recorder(response)).route([A, B])
    assert isinstance(result, RoadRouteUnavailable)
    assert result.reason == reason and result.provider == "osrm"


def test_provider_choice_defaults_keep_the_existing_behaviour() -> None:
    assert settings().effective_routing_provider == "none"
    keyed = settings(google_maps_server_api_key="server-key-value-1234567890")
    assert keyed.effective_routing_provider == "google"
    assert isinstance(build_road_route_provider(keyed), GoogleRoutesProvider)


def test_explicit_provider_wins_and_osrm_needs_a_url() -> None:
    osrm = settings(routing_provider="osrm", osrm_base_url=BASE + "/")
    assert osrm.osrm_base_url == BASE
    provider = build_road_route_provider(osrm)
    assert isinstance(provider, OsrmProvider) and provider.configured
    off = settings(
        routing_provider="none", google_maps_server_api_key="server-key-value-1234567890"
    )
    assert off.effective_routing_provider == "none"
    unconfigured = build_road_route_provider(off)
    assert isinstance(unconfigured, GoogleRoutesProvider) and not unconfigured.configured
    with pytest.raises(ValidationError, match="OSRM_BASE_URL"):
        settings(routing_provider="osrm")
    with pytest.raises(ValidationError, match="GOOGLE_MAPS_SERVER_API_KEY"):
        settings(routing_provider="google")


@pytest.mark.parametrize(
    "url",
    ["ftp://osrm", "osrm:5000", "http://u:p@osrm:5000", "http://osrm:5000?x=1", "http://osrm#f"],
)
def test_osrm_url_must_be_plain_http(url: str) -> None:
    with pytest.raises(ValidationError):
        settings(routing_provider="osrm", osrm_base_url=url)


def test_blank_values_mean_unset() -> None:
    blank = settings(routing_provider="", osrm_base_url="  ")
    assert blank.routing_provider is None and blank.osrm_base_url is None
