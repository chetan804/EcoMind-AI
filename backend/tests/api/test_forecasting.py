"""Forecasting API: series catalogue, honest refusal on short history, backtest evidence,
persistence, labelling of public reference data, authorisation."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.modules.forecasting import engine as forecast_engine
from tests.fixtures.api import ClientFactory, bearer, create_user, login
from tests.fixtures.series import (
    count,
    monday_of,
    seasonal_values,
    seed_platform_weeks,
    seed_reference,
)

BASE = "/api/v1/forecasting"
PLATFORM = "platform:collected_weight_kg"


@dataclass
class Env:
    client: TestClient
    engine: Engine
    ids: dict[str, uuid.UUID]
    h: dict[str, dict[str, str]]


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    client = make_client()
    ids, heads = {}, {}
    for name, roles in (
        ("citizen", ("citizen",)),
        ("collector", ("collector",)),
        ("manager", ("manager",)),
        ("admin", ("administrator",)),
    ):
        ids[name] = create_user(db_engine, email=f"{name}@example.org", roles=roles)
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    return Env(client, db_engine, ids, heads)


def last_complete_week() -> dt.date:
    return monday_of(dt.datetime.now(dt.UTC).date()) - dt.timedelta(days=7)


def platform_weeks(n: int, values: list[float]) -> dict[dt.date, float]:
    end = last_complete_week()
    return {end - dt.timedelta(days=7 * (n - 1 - i)): values[i] for i in range(n)}


def forecast(env: Env, who: str = "manager", **body: Any) -> Any:
    payload: dict[str, Any] = {"series": PLATFORM, "horizon_weeks": 4}
    payload.update(body)
    return env.client.post(f"{BASE}/forecasts", json=payload, headers=env.h[who])


def test_requires_authentication_and_the_right_permission(env: Env) -> None:
    assert env.client.get(f"{BASE}/series").status_code == 401
    for who in ("citizen", "collector"):
        assert env.client.get(f"{BASE}/series", headers=env.h[who]).status_code == 403
        assert forecast(env, who).status_code == 403
    assert env.client.get(f"{BASE}/series", headers=env.h["manager"]).status_code == 200


def test_series_catalogue_labels_platform_and_public_data(env: Env) -> None:
    seed_reference(env.engine, "demo", seasonal_values(120), interpolated={5, 6})
    items = env.client.get(f"{BASE}/series", headers=env.h["manager"]).json()
    by_ref = {i["ref"]: i for i in items}
    assert set(by_ref) == {PLATFORM, "reference:demo"}
    platform, ref = by_ref[PLATFORM], by_ref["reference:demo"]
    assert platform["data_kind"] == "platform" and platform["points"] == 0
    assert platform["provenance"] is None
    assert ref["data_kind"] == "public_reference"
    assert "not produced by this platform" in ref["label"]
    assert ref["interpolated_points"] == 2 and ref["points"] == 120
    assert ref["provenance"]["source_url"] == "https://example.org/test-series"
    assert ref["provenance"]["licence_note"]


def test_history_endpoint_returns_points_and_flags_interpolated_weeks(env: Env) -> None:
    seed_reference(env.engine, "demo", seasonal_values(60), interpolated={3})
    body = env.client.get(
        f"{BASE}/series/history", params={"series": "reference:demo"}, headers=env.h["manager"]
    ).json()
    assert len(body["points"]) == 60
    assert [p["interpolated"] for p in body["points"]].count(True) == 1
    assert body["points"][3]["interpolated"] is True
    assert (
        env.client.get(
            f"{BASE}/series/history", params={"series": "reference:nope"}, headers=env.h["manager"]
        ).status_code
        == 404
    )
    assert (
        env.client.get(
            f"{BASE}/series/history", params={"series": "platform:other"}, headers=env.h["manager"]
        ).status_code
        == 404
    )


def test_platform_series_ignores_the_current_incomplete_week_and_zero_fills_gaps(
    env: Env,
) -> None:
    weeks = platform_weeks(30, [1000.0] * 30)
    del weeks[sorted(weeks)[10]]  # a week with no collection is a true zero
    current = monday_of(dt.datetime.now(dt.UTC).date())
    weeks[current] = 999_999.0  # in-progress week: must not appear
    seed_platform_weeks(env.engine, env.ids["manager"], weeks)
    body = env.client.get(
        f"{BASE}/series/history", params={"series": PLATFORM}, headers=env.h["manager"]
    ).json()
    pts = body["points"]
    assert len(pts) == 30  # 29 weeks with data + 1 zero week, current week excluded
    assert pts[-1]["period_start"] == last_complete_week().isoformat()
    assert pts[10]["value"] == 0.0 and not pts[10]["interpolated"]
    assert max(p["value"] for p in pts) == 1000.0


def test_short_or_empty_history_is_refused_and_nothing_is_stored(env: Env) -> None:
    empty = forecast(env)
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "insufficient_history"
    seed_platform_weeks(env.engine, env.ids["manager"], platform_weeks(10, [500.0] * 10))
    short = forecast(env)
    assert short.status_code == 422
    assert short.json()["error"]["details"][0] == {"available_weeks": 10, "required_weeks": 26}
    assert count(env.engine, "select count(*) from forecast_results") == 0


def test_forecast_on_platform_data_is_stored_with_backtest_evidence_and_audit(env: Env) -> None:
    values = seasonal_values(60, noise=200.0)
    seed_platform_weeks(env.engine, env.ids["manager"], platform_weeks(60, values))
    response = forecast(env, horizon_weeks=6)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["series"]["data_kind"] == "platform"
    assert body["saved"] is True and len(body["points"]) == 6
    first_expected = last_complete_week() + dt.timedelta(days=7)
    assert body["points"][0]["period_start"] == first_expected.isoformat()
    for p in body["points"]:
        assert 0 <= float(p["lower"]) <= float(p["predicted"]) <= float(p["upper"])
    assert body["model"]["engine_version"] == "ts-1.0.0"
    bt = body["backtest"]
    assert bt["origins"] >= 1 and bt["naive_mae"] is not None
    assert "naive" in bt["candidate_mae"] and body["model"]["name"] in bt["candidate_mae"]
    assert any("cannot anticipate" in c for c in body["caveats"])
    assert not any("public reference" in c for c in body["caveats"])
    assert count(env.engine, "select count(*) from forecast_results") == 6
    assert (
        count(env.engine, "select count(*) from audit_logs where action = 'forecast.generated'")
        == 1
    )
    latest = env.client.get(
        f"{BASE}/forecasts/latest", params={"series": PLATFORM}, headers=env.h["manager"]
    ).json()
    assert [p["predicted"] for p in latest["points"]] == [p["predicted"] for p in body["points"]]
    assert latest["model_name"] == body["model"]["name"]


def test_reference_series_forecast_prefers_a_seasonal_model_and_says_it_is_public_data(
    env: Env,
) -> None:
    seed_reference(env.engine, "demo", seasonal_values(220, noise=150.0))
    body = forecast(env, series="reference:demo", horizon_weeks=4).json()
    assert body["series"]["data_kind"] == "public_reference"
    assert body["model"]["name"] in {"seasonal_naive", "holt_winters"}
    assert body["backtest"]["beats_naive"] is True and body["backtest"]["mae_vs_naive"] < 1
    assert any("public reference data" in c for c in body["caveats"])
    assert any("range is approximate" in c for c in body["caveats"])


def test_interpolated_weeks_are_disclosed(env: Env) -> None:
    seed_reference(env.engine, "demo", seasonal_values(100), interpolated={20, 21, 22})
    body = forecast(env, series="reference:demo").json()
    assert any("3 weeks" in c and "interpolated" in c for c in body["caveats"])


def test_save_false_computes_without_writing(env: Env) -> None:
    seed_reference(env.engine, "demo", seasonal_values(100))
    response = forecast(env, series="reference:demo", save=False)
    assert response.status_code == 201 and response.json()["saved"] is False
    assert count(env.engine, "select count(*) from forecast_results") == 0
    assert count(env.engine, "select count(*) from audit_logs where action like 'forecast.%'") == 0


def test_forecast_is_deterministic(env: Env) -> None:
    seed_reference(env.engine, "demo", seasonal_values(150, noise=500.0))
    a = forecast(env, series="reference:demo", save=False).json()
    b = forecast(env, series="reference:demo", save=False).json()
    assert a["points"] == b["points"] and a["model"] == b["model"]


@pytest.mark.parametrize(
    "body",
    [
        {"series": "reference:demo", "horizon_weeks": 0},
        {"series": "reference:demo", "horizon_weeks": 13},
        {"series": "reference:demo", "horizon_weeks": 4, "unexpected": 1},
        {"series": "x"},
    ],
)
def test_invalid_requests_are_rejected(env: Env, body: dict[str, Any]) -> None:
    seed_reference(env.engine, "demo", seasonal_values(100))
    assert (
        env.client.post(f"{BASE}/forecasts", json=body, headers=env.h["manager"]).status_code == 422
    )


def test_unknown_series_is_404(env: Env) -> None:
    assert forecast(env, series="reference:missing").status_code == 404


def test_missing_algorithms_are_a_503_not_invented_numbers(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_reference(env.engine, "demo", seasonal_values(100))
    monkeypatch.setattr(forecast_engine, "MODULE", "ml.time_series.does_not_exist")
    response = forecast(env, series="reference:demo")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "forecast_engine_unavailable"
    assert count(env.engine, "select count(*) from forecast_results") == 0
