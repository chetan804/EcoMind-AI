"""IoT ingestion tests: auth, validation, alerts, simulator labelling."""

from __future__ import annotations

from conftest import api, make_org_with_admin


async def _register_device(client, admin_token, org_id, name="Test Sensor"):
    r = await api(
        client, "POST", "/api/v1/iot/devices", admin_token, org_id,
        json={"name": name, "kind": "fill_sensor"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_valid_device_telemetry_accepted(client):
    org, admin_token = await make_org_with_admin(client)
    device = await _register_device(client, admin_token, org["id"])
    r = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": device["device_key"], "X-Api-Key": device["api_key"]},
        json={"fill_pct": 42.0, "temperature_c": 24.5, "battery_pct": 88.0},
    )
    assert r.status_code == 202, r.text
    # Snapshot updated
    devices = await api(client, "GET", "/api/v1/iot/devices", admin_token, org["id"])
    d = next(x for x in devices.json() if x["id"] == device["id"])
    assert d["current_fill_pct"] == 42.0


async def test_unknown_device_rejected(client):
    org, admin_token = await make_org_with_admin(client)
    r = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": "DOES-NOT-EXIST", "X-Api-Key": "whatever"},
        json={"fill_pct": 10},
    )
    assert r.status_code == 401


async def test_wrong_api_key_rejected(client):
    org, admin_token = await make_org_with_admin(client)
    device = await _register_device(client, admin_token, org["id"])
    r = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": device["device_key"], "X-Api-Key": "emd_wrong_key"},
        json={"fill_pct": 10},
    )
    assert r.status_code == 401


async def test_invalid_payload_rejected(client):
    org, admin_token = await make_org_with_admin(client)
    device = await _register_device(client, admin_token, org["id"])
    r = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": device["device_key"], "X-Api-Key": device["api_key"]},
        json={"fill_pct": 150.0},  # out of range
    )
    assert r.status_code == 422
    r2 = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": device["device_key"], "X-Api-Key": device["api_key"]},
        json={"temperature_c": 500.0},
    )
    assert r2.status_code == 422


async def test_high_fill_triggers_alert_and_notification(client):
    org, admin_token = await make_org_with_admin(client)
    device = await _register_device(client, admin_token, org["id"], name="Overflow Sensor")
    # Default seeded rule: fill >= 85 => high severity
    r = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": device["device_key"], "X-Api-Key": device["api_key"]},
        json={"fill_pct": 93.0},
    )
    assert r.status_code == 202
    alerts = await api(client, "GET", "/api/v1/iot/alerts", admin_token, org["id"])
    items = alerts.json()["items"]
    assert any("85" in (a["message"] or "") or "fill" in a["title"].lower() for a in items)
    assert any(a["severity"] == "high" for a in items)


async def test_high_temperature_triggers_critical_alert(client):
    org, admin_token = await make_org_with_admin(client)
    await api(
        client, "POST", "/api/v1/iot/alert-rules", admin_token, org["id"],
        json={
            "name": "Fire risk",
            "metric": "temperature_c",
            "operator": "gt",
            "threshold": 55,
            "severity": "critical",
        },
    )
    device = await _register_device(client, admin_token, org["id"])
    r = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": device["device_key"], "X-Api-Key": device["api_key"]},
        json={"temperature_c": 61.0},
    )
    assert r.status_code == 202
    alerts = await api(client, "GET", "/api/v1/iot/alerts", admin_token, org["id"])
    assert any(a["severity"] == "critical" for a in alerts.json()["items"])


async def test_alert_cooldown_preuplicates(client):
    org, admin_token = await make_org_with_admin(client)
    device = await _register_device(client, admin_token, org["id"])
    for _ in range(3):
        await client.post(
            "/api/v1/ingest/telemetry",
            headers={"X-Device-Key": device["device_key"], "X-Api-Key": device["api_key"]},
            json={"fill_pct": 90.0},
        )
    alerts = await api(client, "GET", "/api/v1/iot/alerts", admin_token, org["id"])
    fill_alerts = [a for a in alerts.json()["items"] if "fill" in (a["title"] + (a["message"] or "")).lower()]
    assert len(fill_alerts) == 1  # cooldown suppressed duplicates


async def test_revoked_device_rejected(client):
    org, admin_token = await make_org_with_admin(client)
    device = await _register_device(client, admin_token, org["id"])
    await api(client, "PATCH", f"/api/v1/iot/devices/{device['id']}", admin_token, org["id"],
              json={"status": "revoked"})
    r = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": device["device_key"], "X-Api-Key": device["api_key"]},
        json={"fill_pct": 10},
    )
    assert r.status_code == 401


async def test_key_rotation_invalidates_old_key(client):
    org, admin_token = await make_org_with_admin(client)
    device = await _register_device(client, admin_token, org["id"])
    r = await api(client, "POST", f"/api/v1/iot/devices/{device['id']}/rotate-key", admin_token, org["id"])
    new_key = r.json()["api_key"]
    old = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": device["device_key"], "X-Api-Key": device["api_key"]},
        json={"fill_pct": 10},
    )
    assert old.status_code == 401
    new = await client.post(
        "/api/v1/ingest/telemetry",
        headers={"X-Device-Key": device["device_key"], "X-Api-Key": new_key},
        json={"fill_pct": 10},
    )
    assert new.status_code == 202


async def test_simulator_writes_labelled_data_only(client):
    """Simulated telemetry must always carry is_simulated=true."""

    from app.core.db import SessionLocal, tenant_context
    from app.iot.simulator import tick

    org, admin_token = await make_org_with_admin(client)
    r = await api(
        client, "POST", "/api/v1/iot/devices", admin_token, org["id"],
        json={"name": "SIM Sensor", "kind": "fill_sensor", "is_simulated": True},
    )
    sim_device = r.json()
    async with SessionLocal() as session:
        with tenant_context(session, __import__("uuid").UUID(org["id"])):
            await tick(session, organization_id=__import__("uuid").UUID(org["id"]))
            await session.commit()
    devices = await api(client, "GET", "/api/v1/iot/devices", admin_token, org["id"])
    d = next(x for x in devices.json() if x["id"] == sim_device["id"])
    assert d["is_simulated"] is True
    telemetry = await api(client, "GET", f"/api/v1/iot/devices/{sim_device['id']}/telemetry", admin_token, org["id"])
    for reading in telemetry.json()["items"]:
        assert reading["is_simulated"] is True
        assert reading["source"] == "simulator"
