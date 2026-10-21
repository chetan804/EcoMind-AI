"""Community incidents: reporting, privacy, triage lifecycle, notifications."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine

from tests.fixtures.api import ClientFactory, bearer, create_user, login
from tests.fixtures.series import count

BASE = "/api/v1/community-incidents"
MEDIA = "/api/v1/waste-reports/media"


class Env:
    def __init__(self, client: TestClient, engine: Engine) -> None:
        self.client, self.engine = client, engine
        self.ids: dict[str, uuid.UUID] = {}
        self.h: dict[str, dict[str, str]] = {}
        for role, email in (
            ("citizen", "citizen@example.org"),
            ("other", "other@example.org"),
            ("collector", "collector@example.org"),
            ("facility_operator", "operator@example.org"),
            ("manager", "manager@example.org"),
        ):
            self.ids[role] = create_user(
                engine, email=email, roles=("citizen" if role == "other" else role,)
            )
            self.h[role] = bearer(login(client, email)["access_token"])

    def report(self, who: str = "citizen", **over: Any) -> Any:
        body: dict[str, Any] = {
            "incident_type": "illegal_dumping",
            "title": "Mattress dumped on the verge",
            "latitude": "17.385044",
            "longitude": "78.486671",
        }
        body.update(over)
        return self.client.post(BASE, json=body, headers=self.h[who])

    def move(self, incident_id: str, status: str, notes: str | None = None) -> Any:
        body: dict[str, Any] = {"status": status}
        if notes:
            body["notes"] = notes
        return self.client.post(
            f"{BASE}/{incident_id}/status", json=body, headers=self.h["manager"]
        )


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine, tmp_path: Path) -> Env:
    return Env(make_client(file_storage_local_path=tmp_path / "storage"), db_engine)


def test_permissions(env: Env) -> None:
    assert env.client.get(BASE).status_code == 401
    assert env.client.post(BASE, json={}).status_code == 401
    # operators neither report nor view incidents
    assert env.client.get(BASE, headers=env.h["facility_operator"]).status_code == 403
    assert env.report("facility_operator").status_code == 403
    # collectors may report (field staff see problems) and then see what they reported, but never
    # other people's reports: they hold read_own, not triage (audit finding, migration 0016)
    mine = env.report("collector")
    assert mine.status_code == 201
    listed = env.client.get(BASE, headers=env.h["collector"])
    assert listed.status_code == 200
    assert [i["id"] for i in listed.json()["items"]] == [mine.json()["id"]]
    citizens = env.report("citizen").json()["id"]
    assert env.client.get(f"{BASE}/{citizens}", headers=env.h["collector"]).status_code == 404
    for path in ("/summary",):
        assert env.client.get(BASE + path, headers=env.h["citizen"]).status_code == 403
        assert env.client.get(BASE + path, headers=env.h["manager"]).status_code == 200


def test_report_creates_an_open_incident(env: Env) -> None:
    response = env.report(description="Left overnight", address_text="Road 12")
    assert response.status_code == 201, response.text
    inc = response.json()
    assert inc["status"] == "open" and inc["assigned_to_id"] is None
    assert inc["reporter_id"] == str(env.ids["citizen"])
    assert inc["resolved_at"] is None and inc["resolution_notes"] is None
    assert env.client.get(f"{BASE}/{inc['id']}", headers=env.h["citizen"]).json() == inc
    assert (
        count(
            env.engine, "select count(*) from audit_logs where action='community_incident.created'"
        )
        == 1
    )


def test_report_validation(env: Env) -> None:
    cases: dict[str, dict[str, Any]] = {
        "no location": {"latitude": None, "longitude": None},
        "lat only": {"longitude": None},
        "lat out of range": {"latitude": "91"},
        "lon out of range": {"longitude": "-181"},
        "short title": {"title": "ab"},
        "bad type": {"incident_type": "littering"},
        "extra field": {"status": "resolved"},
        "foreign photo": {"photo_media_asset_id": str(uuid.uuid4())},
    }
    for label, over in cases.items():
        base: dict[str, Any] = {
            "incident_type": "other",
            "title": "Valid title",
            "latitude": "17.4",
            "longitude": "78.4",
        }
        body = {k: v for k, v in (base | over).items() if v is not None}
        assert env.client.post(BASE, json=body, headers=env.h["citizen"]).status_code == 422, label
    # an address alone is a sufficient location
    ok = env.client.post(
        BASE,
        json={"incident_type": "other", "title": "Valid title", "address_text": "Near the school"},
        headers=env.h["citizen"],
    )
    assert ok.status_code == 201 and ok.json()["latitude"] is None


def test_photo_must_be_the_reporters_own_upload(env: Env) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 30, 30)).save(buffer, format="PNG")
    up = env.client.post(MEDIA, content=buffer.getvalue(), headers=env.h["citizen"])
    assert up.status_code == 201, up.text
    media_id = up.json()["id"]
    stolen = env.report("other", photo_media_asset_id=media_id)
    assert stolen.status_code == 422
    mine = env.report(photo_media_asset_id=media_id)
    assert mine.status_code == 201
    assert mine.json()["photo_content_path"] == f"{MEDIA}/{media_id}/content"
    # triage staff can open the picture through the existing media endpoint
    assert (
        env.client.get(mine.json()["photo_content_path"], headers=env.h["manager"]).status_code
        == 200
    )


def test_incidents_are_private_to_their_reporter_unless_triaging(env: Env) -> None:
    mine = env.report("citizen").json()
    theirs = env.report(
        "other", title="Overflowing bin at the market", incident_type="overflowing_bin"
    ).json()
    seen = env.client.get(BASE, headers=env.h["citizen"]).json()
    assert [i["id"] for i in seen["items"]] == [mine["id"]]
    assert env.client.get(f"{BASE}/{theirs['id']}", headers=env.h["citizen"]).status_code == 404
    assert env.client.get(f"{BASE}/{uuid.uuid4()}", headers=env.h["citizen"]).status_code == 404
    everything = env.client.get(BASE, headers=env.h["manager"]).json()
    assert everything["total"] == 2
    assert env.client.get(f"{BASE}/{theirs['id']}", headers=env.h["manager"]).status_code == 200
    # a citizen cannot widen their view with filters
    widened = env.client.get(
        BASE,
        params={"assigned_to_id": str(env.ids["manager"]), "unassigned": "true"},
        headers=env.h["citizen"],
    ).json()
    assert [i["id"] for i in widened["items"]] == [mine["id"]]
    # nor act on incidents
    for action, body in (
        ("status", {"status": "acknowledged"}),
        ("assign", {"assignee_id": str(env.ids["collector"])}),
    ):
        assert (
            env.client.post(
                f"{BASE}/{mine['id']}/{action}", json=body, headers=env.h["citizen"]
            ).status_code
            == 403
        )


def test_lifecycle_notifications_and_audit(env: Env) -> None:
    inc = env.report().json()
    iid = inc["id"]
    illegal = [("resolved", "Cleared by crew"), ("in_progress", None)]
    for target, notes in illegal:  # not allowed straight from open
        r = env.move(iid, target, notes)
        assert (
            r.status_code == 409 and r.json()["error"]["code"] == "invalid_incident_transition"
        ), target
    assert env.move(iid, "acknowledged").json()["status"] == "acknowledged"
    assert env.move(iid, "in_progress").json()["status"] == "in_progress"
    assert env.move(iid, "resolved").status_code == 422  # notes are mandatory
    done = env.move(iid, "resolved", "Mattress collected by crew 4")
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "resolved" and body["resolved_at"] is not None
    assert body["resolution_notes"] == "Mattress collected by crew 4"
    for target in ("dismissed", "resolved", "acknowledged", "in_progress"):
        assert env.move(iid, target, "x notes").status_code == 409  # final
    assert env.move(iid, "open", "reopen").status_code == 422  # reopening is not offered
    assert (
        env.client.post(
            f"{BASE}/{uuid.uuid4()}/status",
            json={"status": "acknowledged"},
            headers=env.h["manager"],
        ).status_code
        == 404
    )
    assert (
        env.client.post(
            f"{BASE}/{iid}/status", json={"status": "open"}, headers=env.h["manager"]
        ).status_code
        == 422
    )
    # the reporter heard about every real change, nobody else did
    notes = env.client.get("/api/v1/notifications", headers=env.h["citizen"]).json()
    assert notes["total"] == 3 and {n["category"] for n in notes["items"]} == {"incident"}
    assert env.client.get("/api/v1/notifications", headers=env.h["other"]).json()["total"] == 0
    for action, n in (("acknowledged", 1), ("in_progress", 1), ("resolved", 1)):
        assert (
            count(
                env.engine,
                "select count(*) from audit_logs where action=:a",
                a=f"community_incident.{action}",
            )
            == n
        )


def test_dismissal_needs_a_reason_and_is_final(env: Env) -> None:
    iid = env.report().json()["id"]
    assert env.move(iid, "dismissed").status_code == 422
    out = env.move(iid, "dismissed", "Duplicate of an earlier report")
    assert (
        out.status_code == 200 and out.json()["status"] == "dismissed" and out.json()["resolved_at"]
    )
    assert env.move(iid, "acknowledged").status_code == 409


def test_assignment_rules(env: Env) -> None:
    iid = env.report().json()["id"]
    url = f"{BASE}/{iid}/assign"
    m = env.h["manager"]
    for bad in (str(env.ids["citizen"]), str(env.ids["facility_operator"]), str(uuid.uuid4())):
        assert env.client.post(url, json={"assignee_id": bad}, headers=m).status_code == 422, bad
    ok = env.client.post(url, json={"assignee_id": str(env.ids["collector"])}, headers=m)
    assert ok.status_code == 200 and ok.json()["assigned_to_id"] == str(env.ids["collector"])
    assert env.client.get("/api/v1/notifications", headers=env.h["collector"]).json()["total"] == 1
    reassigned = env.client.post(url, json={"assignee_id": str(env.ids["manager"])}, headers=m)
    assert reassigned.json()["assigned_to_id"] == str(env.ids["manager"])
    env.move(iid, "dismissed", "Not our jurisdiction")
    closed = env.client.post(url, json={"assignee_id": str(env.ids["collector"])}, headers=m)
    assert closed.status_code == 409


def test_filters_summary_and_search(env: Env) -> None:
    a = env.report(title="Dumped sofa near the canal").json()["id"]
    b = env.report("other", incident_type="overflowing_bin", title="Market bin overflowing").json()[
        "id"
    ]
    c = env.report(incident_type="open_burning", title="Smoke from burning tyres").json()["id"]
    env.client.post(
        f"{BASE}/{b}/assign",
        json={"assignee_id": str(env.ids["collector"])},
        headers=env.h["manager"],
    )
    env.move(c, "dismissed", "Verified as a permitted fire")
    m = env.h["manager"]

    def ids(**params: str) -> set[str]:
        return {i["id"] for i in env.client.get(BASE, params=params, headers=m).json()["items"]}

    assert ids(status="open") == {a, b}
    assert ids(status="dismissed") == {c}
    assert ids(incident_type="overflowing_bin") == {b}
    assert ids(unassigned="true") == {a, c}
    assert ids(assigned_to_id=str(env.ids["collector"])) == {b}
    assert ids(q="canal") == {a}
    assert ids(q="%") == set()
    assert env.client.get(BASE, params={"status": "bogus"}, headers=m).status_code == 422
    s = env.client.get(f"{BASE}/summary", headers=m).json()
    assert s["total"] == 3 and s["open_incidents"] == 2 and s["unassigned_open"] == 1
    assert {x["key"]: x["count"] for x in s["by_status"]} == {
        "open": 2, "acknowledged": 0, "in_progress": 0, "resolved": 0, "dismissed": 1,
    }  # fmt: skip
    assert {x["key"]: x["count"] for x in s["by_type"]}["open_burning"] == 1
