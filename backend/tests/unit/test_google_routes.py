"""Google Routes adapter against a mocked transport (no network, no paid calls)."""

from __future__ import annotations

import json
import urllib.error
from typing import Any

import pytest
from pydantic import SecretStr

from app.integrations.mapping.base import LatLng, RoadRoute, RoadRouteUnavailable
from app.integrations.mapping.google_routes import (
    ENDPOINT,
    FIELD_MASK,
    MAX_INTERMEDIATES,
    GoogleRoutesProvider,
    chunk_points,
)

KEY = SecretStr("test-key-not-real-0000000000")
A, B, C = LatLng(17.40, 78.46), LatLng(17.41, 78.47), LatLng(17.42, 78.48)


def ok(distance: int = 1200, duration: str = "300s", poly: str = "_p~iF~ps|U_ulLnnqC") -> bytes:
    return json.dumps(
        {
            "routes": [
                {
                    "distanceMeters": distance,
                    "duration": duration,
                    "polyline": {"encodedPolyline": poly},
                }
            ]
        }
    ).encode()


class Recorder:
    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str], dict[str, Any], float]] = []

    def __call__(
        self, url: str, headers: dict[str, str], body: bytes, timeout: float
    ) -> tuple[int, bytes]:
        self.calls.append((url, headers, json.loads(body), timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return int(response[0]), bytes(response[1])


def provider(*responses: Any, key: SecretStr | None = KEY) -> tuple[GoogleRoutesProvider, Recorder]:
    transport = Recorder(*responses)
    return GoogleRoutesProvider(key, timeout_seconds=3, transport=transport), transport


def test_without_a_key_nothing_is_sent() -> None:
    p, transport = provider(key=None)
    outcome = p.route([A, B])
    assert outcome == RoadRouteUnavailable(reason="not_configured", provider="google_routes")
    assert transport.calls == []
    assert p.configured is False


def test_needs_two_points() -> None:
    p, transport = provider()
    assert isinstance(r := p.route([A]), RoadRouteUnavailable) and r.reason == "too_few_points"
    assert transport.calls == []


def test_request_shape_key_in_header_and_minimal_field_mask() -> None:
    p, transport = provider((200, ok()))
    outcome = p.route([A, B, C, A])
    assert isinstance(outcome, RoadRoute)
    (url, headers, body, timeout) = transport.calls[0]
    assert url == ENDPOINT and "key=" not in url  # the key never appears in the URL
    assert headers["X-Goog-Api-Key"] == KEY.get_secret_value()
    assert headers["X-Goog-FieldMask"] == FIELD_MASK
    assert timeout == 3
    assert body["travelMode"] == "DRIVE" and body["routingPreference"] == "TRAFFIC_UNAWARE"
    assert body["origin"]["location"]["latLng"] == {"latitude": 17.40, "longitude": 78.46}
    assert len(body["intermediates"]) == 2
    assert outcome.distance_m == 1200 and outcome.duration_s == 300
    assert outcome.traffic_aware is False and outcome.request_count == 1


def test_long_routes_are_chunked_and_summed() -> None:
    points = [LatLng(17.0 + i * 0.001, 78.0) for i in range(30)]
    segments = chunk_points(points)
    assert all(len(s) <= MAX_INTERMEDIATES + 2 for s in segments)
    assert segments[0][-1] == segments[1][0]  # chunks share their end points
    assert segments[-1][-1] == points[-1]
    assert sum(len(s) - 1 for s in segments) == len(points) - 1  # every leg exactly once
    p, transport = provider(*[(200, ok(1000, "60s", f"poly{i}")) for i in range(len(segments))])
    outcome = p.route(points)
    assert isinstance(outcome, RoadRoute)
    assert outcome.request_count == len(segments) == len(transport.calls)
    assert outcome.distance_m == 1000 * len(segments) and outcome.duration_s == 60 * len(segments)
    assert outcome.encoded_polylines == tuple(f"poly{i}" for i in range(len(segments)))


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (401, "access_denied"),
        (403, "access_denied"),
        (429, "quota_exceeded"),
        (500, "provider_error"),
        (400, "provider_error"),
    ],
)
def test_error_statuses_are_classified(status: int, reason: str) -> None:
    p, _ = provider((status, b'{"error": {"message": "secret detail"}}'))
    outcome = p.route([A, B])
    assert isinstance(outcome, RoadRouteUnavailable) and outcome.reason == reason
    assert "secret detail" not in repr(outcome)  # provider text is not passed through


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (TimeoutError(), "timeout"),
        (urllib.error.URLError(TimeoutError()), "timeout"),
        (urllib.error.URLError("dns failure"), "network_error"),
        (ConnectionResetError(), "network_error"),
    ],
)
def test_network_failures_are_classified(failure: BaseException, reason: str) -> None:
    p, _ = provider(failure)
    outcome = p.route([A, B])
    assert isinstance(outcome, RoadRouteUnavailable) and outcome.reason == reason


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (b"not json", "bad_response"),
        (b"{}", "no_route"),
        (b'{"routes": []}', "no_route"),
        (json.dumps({"routes": [{"distanceMeters": 5}]}).encode(), "bad_response"),
        (ok(duration="abc"), "bad_response"),
        (ok(poly=""), "bad_response"),
        (ok(distance=-5), "bad_response"),
    ],
)
def test_malformed_responses_are_never_turned_into_routes(payload: bytes, reason: str) -> None:
    p, _ = provider((200, payload))
    outcome = p.route([A, B])
    assert isinstance(outcome, RoadRouteUnavailable) and outcome.reason == reason


def test_a_failing_chunk_fails_the_whole_route() -> None:
    points = [LatLng(17.0 + i * 0.001, 78.0) for i in range(15)]
    p, transport = provider((200, ok()), (429, b""))
    outcome = p.route(points)
    assert isinstance(outcome, RoadRouteUnavailable) and outcome.reason == "quota_exceeded"
    assert len(transport.calls) == 2  # no partial route is returned
