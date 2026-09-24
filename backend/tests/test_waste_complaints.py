"""Waste report + complaint lifecycle tests."""

from __future__ import annotations

from conftest import add_member, api, make_org_with_admin, register_user


async def test_report_lifecycle(client):
    org, admin_token = await make_org_with_admin(client)
    citizen, citizen_token = await add_member(client, admin_token, org["id"], role="citizen")

    r = await api(
        client, "POST", "/api/v1/waste/reports", citizen_token, org["id"],
        json={"description": "heap of plastic bottles and paper near bus stop", "latitude": 12.94, "longitude": 77.60},
    )
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["status"] == "submitted"

    # Heuristic baseline classified from text and flags review (confidence 0.45 < 0.75)
    assert report["ai_inference_id"] is not None
    assert report["ai_category"] == "recyclable"
    assert report["ai_confidence"] is not None

    # Timeline exists
    t = await api(client, "GET", f"/api/v1/waste/reports/{report['id']}/timeline", citizen_token, org["id"])
    assert t.status_code == 200
    assert any(e["event_type"] == "created" for e in t.json())

    # Invalid transition rejected
    bad = await api(
        client, "PATCH", f"/api/v1/waste/reports/{report['id']}/status", citizen_token, org["id"],
        json={"status": "closed"},
    )
    assert bad.status_code == 422

    # Citizen cannot resolve (needs report:resolve)
    r2 = await api(
        client, "PATCH", f"/api/v1/waste/reports/{report['id']}/status", admin_token, org["id"],
        json={"status": "triaged", "severity": "high", "note": "verified by ops"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "triaged"
    assert r2.json()["severity"] == "high"

    r3 = await api(
        client, "PATCH", f"/api/v1/waste/reports/{report['id']}/status", admin_token, org["id"],
        json={"status": "resolved", "resolution_notes": "collected by crew"},
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "resolved"


async def test_report_assignment_requires_membership(client):
    org, admin_token = await make_org_with_admin(client)
    citizen, citizen_token = await add_member(client, admin_token, org["id"], role="citizen")
    r = await api(
        client, "POST", "/api/v1/waste/reports", citizen_token, org["id"],
        json={"description": "organic waste", "latitude": 12.94, "longitude": 77.60},
    )
    report = r.json()
    outsider = await register_user(client)
    r2 = await api(
        client, "POST", f"/api/v1/waste/reports/{report['id']}/assign", admin_token, org["id"],
        json={"user_id": outsider["user"]["id"]},
    )
    assert r2.status_code == 422  # not a member of this org


async def test_invalid_coordinates_rejected(client):
    org, admin_token = await make_org_with_admin(client)
    r = await api(
        client, "POST", "/api/v1/waste/reports", admin_token, org["id"],
        json={"description": "x", "latitude": 999.0, "longitude": 77.6},
    )
    assert r.status_code == 422


async def test_anonymous_reporting_disabled_by_default(client):
    org, admin_token = await make_org_with_admin(client)
    r = await client.post(
        "/api/v1/waste/reports/anonymous",
        data={"org_slug": org["slug"], "description": "dumping", "latitude": "12.94", "longitude": "77.60"},
    )
    assert r.status_code == 422


async def test_anonymous_reporting_with_opt_in_and_rate_limit(client):
    org, admin_token = await make_org_with_admin(client)
    # Opt in
    r = await api(client, "PATCH", "/api/v1/organizations/current", admin_token, org["id"],
                  json={"allow_anonymous_reports": True})
    assert r.status_code == 200
    r = await client.post(
        "/api/v1/waste/reports/anonymous",
        data={"org_slug": org["slug"], "description": "illegal dumping of construction debris",
              "latitude": "12.94", "longitude": "77.60"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_anonymous"] is True
    # Abuse prevention: exhaust the anonymous budget
    codes = []
    for _ in range(6):
        rr = await client.post(
            "/api/v1/waste/reports/anonymous",
            data={"org_slug": org["slug"], "description": "more", "latitude": "12.94", "longitude": "77.60"},
        )
        codes.append(rr.status_code)
    assert 403 in codes


async def test_complaint_lifecycle_with_sla(client):
    org, admin_token = await make_org_with_admin(client)
    citizen, citizen_token = await add_member(client, admin_token, org["id"], role="citizen")

    r = await api(
        client, "POST", "/api/v1/complaints", citizen_token, org["id"],
        json={"subject": "Bin not collected on Tuesday", "description": "The collection vehicle missed our street",
              "category": "other"},
    )
    assert r.status_code == 201, r.text
    complaint = r.json()
    # AI suggests missed_collection (keyword baseline) — suggestion only
    assert complaint["category"] == "missed_collection"
    assert complaint["due_at"] is not None  # SLA set

    staff, staff_token = await add_member(client, admin_token, org["id"], role="ops_manager")
    r2 = await api(
        client, "PATCH", f"/api/v1/complaints/{complaint['id']}", staff_token, org["id"],
        json={"priority": "high", "assignee": staff["id"], "new_status": "assigned"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "assigned"

    r3 = await api(
        client, "PATCH", f"/api/v1/complaints/{complaint['id']}", staff_token, org["id"],
        json={"new_status": "resolved", "resolution_summary": "Extra pickup completed"},
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "resolved"

    # Citizen sees comments (non-internal only)
    await api(
        client, "POST", f"/api/v1/complaints/{complaint['id']}/comments", staff_token, org["id"],
        json={"body": "Visible update", "is_internal": False},
    )
    await api(
        client, "POST", f"/api/v1/complaints/{complaint['id']}/comments", staff_token, org["id"],
        json={"body": "Internal note for staff", "is_internal": True},
    )
    visible = await api(client, "GET", f"/api/v1/complaints/{complaint['id']}/comments", citizen_token, org["id"])
    bodies = [c["body"] for c in visible.json()]
    assert "Visible update" in bodies
    assert "Internal note for staff" not in bodies
