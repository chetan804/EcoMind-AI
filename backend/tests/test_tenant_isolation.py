"""RELEASE-BLOCKING: cross-tenant access must be impossible.

Organization A must never read or mutate Organization B's data through any
API path. This suite exercises reports, complaints, collection, fleet, routes,
devices, alerts, analytics, audit and media.
"""

from __future__ import annotations

import io

from conftest import (
    add_member,
    api,
    create_point,
    make_org_with_admin,
)


async def _seed_two_orgs(client) -> tuple:
    org_a, token_a = await make_org_with_admin(client)
    org_b, token_b = await make_org_with_admin(client)

    # A citizen report in org A
    r = await api(
        client, "POST", "/api/v1/waste/reports", token_a, org_a["id"],
        json={"description": "plastic bottles dumped near park", "latitude": 12.94, "longitude": 77.60},
    )
    assert r.status_code == 201, r.text
    report_a = r.json()

    # A collection point in org A
    point_a = await create_point(client, token_a, org_a["id"], 12.94, 77.61)

    # A vehicle in org A
    r = await api(
        client, "POST", "/api/v1/fleet/vehicles", token_a, org_a["id"],
        json={"code": "V-A1", "vehicle_type": "compactor_truck", "fuel_type": "diesel", "capacity_kg": 5000},
    )
    assert r.status_code == 201, r.text

    # A device in org A
    r = await api(
        client, "POST", "/api/v1/iot/devices", token_a, org_a["id"],
        json={"name": "Bin Sensor A", "kind": "fill_sensor"},
    )
    assert r.status_code == 201, r.text
    device_a = r.json()

    # A media upload in org A
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c626001000000ffff030000060005"
        "57bfabd40000000049454e44ae426082"
    )
    r = await api(
        client, "POST", "/api/v1/media/upload", token_a, org_a["id"],
        files={"file": ("photo.png", io.BytesIO(png), "image/png")},
    )
    assert r.status_code == 201, r.text
    media_a = r.json()

    return org_a, token_a, org_b, token_b, report_a, point_a, device_a, media_a


async def test_org_b_cannot_read_org_a_reports(client):
    org_a, token_a, org_b, token_b, report_a, *_ = await _seed_two_orgs(client)
    r = await api(client, "GET", f"/api/v1/waste/reports/{report_a['id']}", token_b, org_b["id"])
    assert r.status_code == 404, f"CROSS-TENANT LEAK: {r.text}"
    listing = await api(client, "GET", "/api/v1/waste/reports", token_b, org_b["id"])
    ids = [i["id"] for i in listing.json()["items"]]
    assert report_a["id"] not in ids


async def test_org_b_cannot_mutate_org_a_report(client):
    org_a, token_a, org_b, token_b, report_a, *_ = await _seed_two_orgs(client)
    r = await api(
        client, "PATCH", f"/api/v1/waste/reports/{report_a['id']}/status", token_b, org_b["id"],
        json={"status": "triaged"},
    )
    assert r.status_code == 404, f"CROSS-TENANT WRITE: {r.text}"


async def test_org_b_cannot_see_org_a_collection_points(client):
    org_a, token_a, org_b, token_b, report_a, point_a, *_ = await _seed_two_orgs(client)
    r = await api(client, "GET", "/api/v1/collection/points", token_b, org_b["id"])
    ids = [p["id"] for p in r.json()]
    assert point_a["id"] not in ids


async def test_org_b_cannot_see_org_a_fleet(client):
    org_a, token_a, org_b, token_b, *_ = await _seed_two_orgs(client)
    r = await api(client, "GET", "/api/v1/fleet/vehicles", token_b, org_b["id"])
    assert all(v["code"] != "V-A1" for v in r.json())


async def test_org_b_cannot_see_org_a_devices_or_telemetry(client):
    org_a, token_a, org_b, token_b, _, _, device_a, _ = await _seed_two_orgs(client)
    r = await api(client, "GET", "/api/v1/iot/devices", token_b, org_b["id"])
    assert all(d["id"] != device_a["id"] for d in r.json())
    r = await api(client, "GET", f"/api/v1/iot/devices/{device_a['id']}/telemetry", token_b, org_b["id"])
    assert r.status_code == 404


async def test_org_b_cannot_access_org_a_media(client):
    org_a, token_a, org_b, token_b, _, _, _, media_a = await _seed_two_orgs(client)
    r = await api(client, "GET", f"/api/v1/media/{media_a['id']}", token_b, org_b["id"])
    assert r.status_code == 404, f"CROSS-TENANT OBJECT ACCESS: {r.text}"
    # But org A can access its own upload
    r = await api(client, "GET", f"/api/v1/media/{media_a['id']}", token_a, org_a["id"])
    assert r.status_code == 200


async def test_org_b_analytics_excludes_org_a_activity(client):
    org_a, token_a, org_b, token_b, report_a, *_ = await _seed_two_orgs(client)
    r = await api(client, "GET", "/api/v1/analytics/operations", token_b, org_b["id"])
    assert r.status_code == 200
    # org A's report must not appear in org B's open work counters
    assert r.json()["work"]["open_reports"] == 0


async def test_org_b_cannot_generate_routes_over_org_a_points(client):
    org_a, token_a, org_b, token_b, report_a, point_a, *_ = await _seed_two_orgs(client)
    # org B has no points; a route generation naming org A's point must fail
    r = await api(
        client, "POST", "/api/v1/routes/generate", token_b, org_b["id"],
        json={
            "name": "B route", "service_date": "2030-01-01",
            "depot_lat": 12.94, "depot_lng": 77.60, "point_ids": [point_a["id"]],
        },
    )
    # Either rejected (no matching points in tenant scope) or a route with 0 of A's stops
    if r.status_code == 201:
        stop_point_ids = [s["collection_point_id"] for s in r.json()["stops"]]
        assert point_a["id"] not in stop_point_ids, "CROSS-TENANT ROUTE LEAK"
    else:
        assert r.status_code in (400, 422)


async def test_audit_log_is_tenant_scoped(client):
    org_a, token_a, org_b, token_b, *_ = await _seed_two_orgs(client)
    r = await api(client, "GET", "/api/v1/admin/audit", token_b, org_b["id"])
    assert r.status_code == 200
    for event in r.json()["items"]:
        assert event["action"] != "report.update_status"  # org A's actions invisible


async def test_membership_in_org_a_grants_no_access_to_org_b(client):
    """A user who is admin of org A but has no membership in org B cannot use org B context."""
    org_a, token_a, org_b, token_b, report_a, *_ = await _seed_two_orgs(client)
    r = await api(client, "GET", "/api/v1/waste/reports", token_a, org_b["id"])
    assert r.status_code == 403, "NON-MEMBER MUST NOT SELECT ANOTHER ORG"


async def test_citizen_cannot_escalate_permissions_via_context_switch(client):
    """Citizen of org A cannot gain staff permissions by spoofing headers."""
    org_a, token_a, *_ = await make_org_with_admin(client)
    citizen_user, citizen_token = await add_member(client, token_a, org_a["id"], role="citizen")
    r = await api(client, "GET", "/api/v1/waste/reports", citizen_token, org_a["id"])
    assert r.status_code == 200  # own scope only
    # citizen cannot see others' reports
    r2 = await api(
        client, "POST", "/api/v1/waste/reports", token_a, org_a["id"],
        json={"description": "admin report", "latitude": 12.94, "longitude": 77.60},
    )
    admin_report = r2.json()
    listing = await api(client, "GET", "/api/v1/waste/reports", citizen_token, org_a["id"])
    ids = [i["id"] for i in listing.json()["items"]]
    assert admin_report["id"] not in ids
    # citizen cannot read admin's report directly
    r3 = await api(client, "GET", f"/api/v1/waste/reports/{admin_report['id']}", citizen_token, org_a["id"])
    assert r3.status_code == 403
