"""Anomaly detection API: detection on known deviations, idempotent scans, honest wording,
platform vs public-data separation, alert lifecycle and authorisation."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.fixtures.api import ClientFactory, bearer, create_user, login
from tests.fixtures.series import (
    count,
    monday_of,
    seasonal_values,
    seed_platform_weeks,
    seed_reference,
)

BASE = "/api/v1/anomalies"
PLATFORM = "platform:collected_weight_kg"
SPIKE, DROP = 180, 195  # indexes in a 220-week series (after the 104-week warm-up)


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
        ("operator", ("facility_operator",)),
        ("manager", ("manager",)),
    ):
        ids[name] = create_user(db_engine, email=f"{name}@example.org", roles=roles)
        heads[name] = bearer(login(client, f"{name}@example.org")["access_token"])
    return Env(client, db_engine, ids, heads)


def injected_series() -> list[float]:
    values = seasonal_values(220, noise=200.0)
    values[SPIKE] *= 2.8
    values[DROP] *= 0.2
    return values


def scan(env: Env, who: str = "manager", **body: Any) -> Any:
    payload: dict[str, Any] = {"series": "reference:demo", "lookback_weeks": 100}
    payload.update(body)
    return env.client.post(f"{BASE}/scan", json=payload, headers=env.h[who])


def test_permissions(env: Env) -> None:
    assert env.client.get(BASE).status_code == 401
    for who in ("citizen", "collector"):
        assert env.client.get(BASE, headers=env.h[who]).status_code == 403
        assert scan(env, who).status_code == 403
    # facility operators hold neither anomalies:read nor anomalies:manage
    assert env.client.get(BASE, headers=env.h["operator"]).status_code == 403
    assert scan(env, "operator").status_code == 403
    assert env.client.get(BASE, headers=env.h["manager"]).status_code == 200


def test_scan_finds_the_injected_spike_and_drop_with_honest_wording(env: Env) -> None:
    weeks = seed_reference(env.engine, "demo", injected_series())
    body = scan(env).json()
    assert body["data_kind"] == "public_reference"
    assert "Suspected anomalies only" in body["caveat"]
    found = {a["window_start"][:10]: a for a in body["alerts"]}
    spike, drop = found[weeks[SPIKE].isoformat()], found[weeks[DROP].isoformat()]
    assert spike["severity"] == "critical" and drop["severity"] == "critical"
    assert float(spike["observed_value"]) > float(spike["expected_value"])
    assert float(drop["observed_value"]) < float(drop["expected_value"])
    assert "higher than expected" in spike["explanation"]
    assert "lower than expected" in drop["explanation"]
    for a in (spike, drop):
        assert "Suspected anomaly, not a confirmed incident" in a["explanation"]
        assert "Public reference data" in a["explanation"]
        assert a["status"] == "open" and a["data_kind"] == "public_reference"
        assert float(a["threshold_value"]) > 0
    assert body["created"] == len(body["alerts"]) >= 2
    assert body["weeks_scanned"] == 220


def test_scan_is_idempotent(env: Env) -> None:
    seed_reference(env.engine, "demo", injected_series())
    first = scan(env).json()
    second = scan(env).json()
    assert second["created"] == 0 and second["already_recorded"] == first["created"]
    assert second["flagged"] == first["flagged"]
    assert count(env.engine, "select count(*) from anomaly_alerts") == first["created"]


def test_lookback_limits_which_weeks_are_considered(env: Env) -> None:
    weeks = seed_reference(env.engine, "demo", injected_series())
    recent = scan(env, lookback_weeks=10).json()  # spike at 180 and drop at 195 of 220
    starts = {a["window_start"][:10] for a in recent["alerts"]}
    assert weeks[SPIKE].isoformat() not in starts
    assert recent["weeks_considered"] == 10


def test_interpolated_weeks_never_raise_alerts(env: Env) -> None:
    seed_reference(env.engine, "demo", injected_series(), interpolated={SPIKE, DROP})
    body = scan(env).json()
    starts = {a["window_start"][:10] for a in body["alerts"]}
    assert not starts & {
        (dt.date(2015, 1, 5) + dt.timedelta(days=7 * i)).isoformat() for i in (SPIKE, DROP)
    }


def test_clean_seasonal_series_is_quiet(env: Env) -> None:
    seed_reference(env.engine, "demo", seasonal_values(220, noise=100.0))
    assert scan(env).json()["created"] == 0  # deterministic seed: no false alarms


def test_short_history_is_refused(env: Env) -> None:
    seed_reference(env.engine, "demo", seasonal_values(10))
    response = scan(env)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "insufficient_history"
    assert scan(env, series="reference:unknown").status_code == 404
    assert scan(env, series=PLATFORM).status_code == 422  # platform has no data yet


def test_platform_series_uses_the_level_rule_when_history_is_short(env: Env) -> None:
    end = monday_of(dt.datetime.now(dt.UTC).date()) - dt.timedelta(days=7)
    values = seasonal_values(40, amp=0.0, noise=100.0)
    values[-3] = 90_000.0
    weeks = {end - dt.timedelta(days=7 * (39 - i)): v for i, v in enumerate(values)}
    seed_platform_weeks(env.engine, env.ids["manager"], weeks)
    body = scan(env, series=PLATFORM, lookback_weeks=8).json()
    assert body["data_kind"] == "platform"
    assert "previous three weeks" in body["detector"]
    assert body["created"] >= 1
    alert = body["alerts"][0]
    assert alert["data_kind"] == "platform" and alert["severity"] == "critical"
    listed = env.client.get(BASE, headers=env.h["manager"]).json()
    assert listed["total"] == body["created"]  # default list = platform data only


def test_public_reference_alerts_are_kept_out_of_the_default_list(env: Env) -> None:
    seed_reference(env.engine, "demo", injected_series())
    created = scan(env).json()["created"]
    default = env.client.get(BASE, headers=env.h["manager"]).json()
    assert default["total"] == 0
    ref = env.client.get(
        BASE, params={"data_kind": "public_reference", "page_size": 100}, headers=env.h["manager"]
    ).json()
    assert ref["total"] == created
    critical = env.client.get(
        BASE,
        params={"data_kind": "public_reference", "severity": "critical"},
        headers=env.h["manager"],
    ).json()
    assert critical["total"] >= 2
    one = ref["items"][0]
    assert env.client.get(f"{BASE}/{one['id']}", headers=env.h["manager"]).json()["id"] == one["id"]
    assert env.client.get(f"{BASE}/{uuid.uuid4()}", headers=env.h["manager"]).status_code == 404


def first_alert(env: Env) -> dict[str, Any]:
    seed_reference(env.engine, "demo", injected_series())
    return dict(scan(env).json()["alerts"][0])


def test_alert_lifecycle_and_audit(env: Env) -> None:
    alert = first_alert(env)
    url = f"{BASE}/{alert['id']}"
    ack = env.client.post(f"{url}/acknowledge", json={"note": "looking"}, headers=env.h["manager"])
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged"
    assert ack.json()["acknowledged_by_id"] == str(env.ids["manager"])
    done = env.client.post(f"{url}/resolve", json={}, headers=env.h["manager"])
    assert done.json()["status"] == "resolved" and done.json()["resolved_at"]
    # terminal: nothing further is possible
    for verb in ("acknowledge", "resolve", "false-positive"):
        again = env.client.post(f"{url}/{verb}", json={}, headers=env.h["manager"])
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "invalid_alert_transition"
    actions = {
        "anomaly_alert.acknowledged": 1,
        "anomaly_alert.resolved": 1,
    }
    for action, expected in actions.items():
        assert (
            count(env.engine, "select count(*) from audit_logs where action = :a", a=action)
            == expected
        )


def test_false_positive_directly_from_open_records_who_reviewed(env: Env) -> None:
    alert = first_alert(env)
    response = env.client.post(
        f"{BASE}/{alert['id']}/false-positive",
        json={"note": "Public holiday closure"},
        headers=env.h["manager"],
    )
    body = response.json()
    assert response.status_code == 200 and body["status"] == "false_positive"
    assert body["acknowledged_by_id"] == str(env.ids["manager"])
    assert (
        count(
            env.engine,
            "select count(*) from audit_logs where action = 'anomaly_alert.false_positive' "
            "and changes ->> 'note' = 'Public holiday closure'",
        )
        == 1
    )


def test_only_managers_change_alerts_and_bad_bodies_are_rejected(env: Env) -> None:
    alert = first_alert(env)
    url = f"{BASE}/{alert['id']}/acknowledge"
    for who in ("citizen", "collector", "operator"):
        assert env.client.post(url, json={}, headers=env.h[who]).status_code == 403
    assert env.client.post(url, json={"note": ""}, headers=env.h["manager"]).status_code == 422
    assert env.client.post(url, json={"x": 1}, headers=env.h["manager"]).status_code == 422
    assert (
        env.client.post(
            f"{BASE}/{uuid.uuid4()}/acknowledge", json={}, headers=env.h["manager"]
        ).status_code
        == 404
    )
    assert scan(env, lookback_weeks=0).status_code == 422
