"""Material passports and chain of custody: state machine, linkage, append-only history."""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.fixtures.chain import Chain, chain  # noqa: F401 (fixture)
from tests.fixtures.series import count

BASE = "/api/v1/material-passports"
RECOVERY = "/api/v1/circular-economy/recovery-records"


def new(c: Chain, who: str = "facility_operator", **over: Any) -> Any:
    body: dict[str, Any] = {
        "material_category_id": c.category("plastic"),
        "weight_kg": "42.500",
        "description": "Baled PET",
        "current_facility_id": c.facility("A"),
    }
    body.update(over)
    return c.client.post(BASE, json=body, headers=c.h[who])


def event(c: Chain, pid: str, kind: str, who: str = "facility_operator", **body: Any) -> Any:
    return c.client.post(
        f"{BASE}/{pid}/events", json={"event_type": kind, **body}, headers=c.h[who]
    )


def recovery_record(c: Chain, category: str = "plastic", *, verified: bool = False) -> str:
    created = c.client.post(
        RECOVERY,
        json={
            "facility_id": c.facility("A"),
            "material_category_id": c.category(category),
            "recovery_method": "recycled",
            "input_weight_kg": "42.5",
            "recovered_weight_kg": "40",
            "processed_at": (dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)).isoformat(),
        },
        headers=c.h["facility_operator"],
    ).json()["id"]
    if verified:
        r = c.client.post(
            f"{RECOVERY}/{created}/verify", json={"decision": "verified"}, headers=c.h["manager"]
        )
        assert r.status_code == 200, r.text
    return str(created)


def test_permissions(chain: Chain) -> None:  # noqa: F811
    assert chain.client.get(BASE).status_code == 401
    for who in ("citizen", "collector"):
        assert chain.client.get(BASE, headers=chain.h[who]).status_code == 403
        assert new(chain, who).status_code == 403
    pid = new(chain).json()["id"]
    assert chain.client.get(f"{BASE}/{pid}", headers=chain.h["manager"]).status_code == 200
    assert (
        event(chain, pid, "received", "citizen", to_facility_id=chain.facility("A")).status_code
        == 403
    )


def test_create_writes_the_first_custody_event(chain: Chain) -> None:  # noqa: F811
    response = new(chain)
    assert response.status_code == 201, response.text
    p = response.json()
    assert re.fullmatch(r"MP-[A-HJ-NP-Z2-9]{10}", p["passport_code"])
    assert p["status"] == "active" and p["created_by_id"] == str(chain.ids["facility_operator"])
    assert [(e["sequence"], e["event_type"]) for e in p["events"]] == [(1, "created")]
    assert p["events"][0]["actor_id"] == str(chain.ids["facility_operator"])
    assert chain.client.get(f"{BASE}/{p['id']}", headers=chain.h["manager"]).json() == p
    by_code = chain.client.get(
        f"{BASE}/by-code/{p['passport_code'].lower()}", headers=chain.h["manager"]
    )
    assert by_code.status_code == 200 and by_code.json()["id"] == p["id"]
    assert (
        chain.client.get(f"{BASE}/by-code/MP-NOPE", headers=chain.h["manager"]).status_code == 404
    )
    assert new(chain).json()["passport_code"] != p["passport_code"]


def test_create_validation(chain: Chain) -> None:  # noqa: F811
    pending = chain.client.post(
        "/api/v1/collection/tasks",
        json={"title": "Open", "address_text": "1 Road"},
        headers=chain.h["manager"],
    ).json()["id"]
    cases = {
        "zero weight": {"weight_kg": "0"},
        "negative weight": {"weight_kg": "-3"},
        "unknown category": {"material_category_id": str(uuid.uuid4())},
        "unknown facility": {"current_facility_id": str(uuid.uuid4())},
        "task not completed": {"origin_collection_task_id": pending},
        "unknown task": {"origin_collection_task_id": str(uuid.uuid4())},
        "extra field": {"status": "recovered"},
    }
    for label, over in cases.items():
        assert new(chain, **over).status_code == 422, label
    done = chain.completed_task()
    ok = new(chain, origin_collection_task_id=done)
    assert ok.status_code == 201 and ok.json()["origin_collection_task_id"] == done


def test_full_chain_to_recovered(chain: Chain) -> None:  # noqa: F811
    a, b = chain.facility("A"), chain.facility("B")
    pid = new(chain).json()["id"]
    assert event(chain, pid, "received", to_facility_id=a).status_code == 201
    out = event(chain, pid, "transferred", to_facility_id=b, notes="to sorting line").json()
    assert out["current_facility_id"] is None  # in transit
    got = event(chain, pid, "received", to_facility_id=b).json()
    assert got["current_facility_id"] == b and got["status"] == "active"
    assert event(chain, pid, "processed").json()["status"] == "in_processing"

    # not verifiable until a verified recovery record is linked
    assert event(chain, pid, "verified").status_code == 409
    record = recovery_record(chain)
    link = chain.client.post(
        f"{BASE}/{pid}/recovery",
        json={"recovery_record_id": record},
        headers=chain.h["facility_operator"],
    )
    assert link.status_code == 200 and link.json()["recovery_record_id"] == record
    still_pending = event(chain, pid, "verified")
    assert still_pending.status_code == 409
    assert still_pending.json()["error"]["code"] == "invalid_custody_event"
    chain.client.post(
        f"{RECOVERY}/{record}/verify", json={"decision": "verified"}, headers=chain.h["manager"]
    )
    final = event(chain, pid, "verified")
    assert final.status_code == 201 and final.json()["status"] == "recovered"
    body = final.json()
    assert [e["sequence"] for e in body["events"]] == [1, 2, 3, 4, 5, 6]
    assert [e["event_type"] for e in body["events"]] == [
        "created", "received", "transferred", "received", "processed", "verified",
    ]  # fmt: skip
    closed = event(chain, pid, "received", to_facility_id=a)
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "passport_closed"

    check = chain.client.get(f"{BASE}/{pid}/integrity", headers=chain.h["manager"]).json()
    assert check["valid"] is True and check["events"] == 6 and check["problems"] == []
    assert "not a cryptographic proof" in check["basis"]
    assert (
        count(
            chain.engine, "select count(*) from audit_logs where action like 'material_passport.%'"
        )
        == 7  # created + 5 custody events + recovery link
    )


def test_invalid_event_sequences_and_arguments(chain: Chain) -> None:  # noqa: F811
    a, b = chain.facility("A"), chain.facility("B")
    pid = new(chain).json()["id"]
    for kind in ("created", "processed", "verified"):
        r = event(chain, pid, kind)
        assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_custody_event", kind
    assert event(chain, pid, "received").status_code == 422  # needs a destination
    assert event(chain, pid, "transferred", to_facility_id=a).status_code == 422  # same facility
    assert event(chain, pid, "received", to_facility_id=str(uuid.uuid4())).status_code == 422
    closed = chain.facility("SHUT", status="inactive")
    assert event(chain, pid, "received", to_facility_id=closed).status_code == 422
    future = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=2)).isoformat()
    assert event(chain, pid, "received", to_facility_id=b, occurred_at=future).status_code == 422
    assert (
        event(
            chain, pid, "received", to_facility_id=b, occurred_at="2026-01-01T00:00:00"
        ).status_code
        == 422
    )
    long_ago = dt.datetime(2001, 1, 1, tzinfo=dt.UTC).isoformat()
    assert event(chain, pid, "received", to_facility_id=b, occurred_at=long_ago).status_code == 422
    assert event(chain, pid, "teleported").status_code == 422
    assert event(chain, str(uuid.uuid4()), "received", to_facility_id=a).status_code == 404
    # nothing above changed the chain
    assert len(chain.client.get(f"{BASE}/{pid}", headers=chain.h["manager"]).json()["events"]) == 1


def test_processing_needs_the_batch_at_a_facility(chain: Chain) -> None:  # noqa: F811
    a, b = chain.facility("A"), chain.facility("B")
    pid = new(chain, current_facility_id=None).json()["id"]
    assert event(chain, pid, "received", to_facility_id=a).status_code == 201
    assert event(chain, pid, "transferred", to_facility_id=b).status_code == 201  # now in transit
    r = event(chain, pid, "processed")
    assert r.status_code == 409  # processed cannot follow transferred


def test_linking_a_recovery_record(chain: Chain) -> None:  # noqa: F811
    pid = new(chain).json()["id"]

    def link(record: str) -> Any:
        return chain.client.post(
            f"{BASE}/{pid}/recovery",
            json={"recovery_record_id": record},
            headers=chain.h["facility_operator"],
        )

    assert link(str(uuid.uuid4())).status_code == 422
    assert link(recovery_record(chain, "glass")).status_code == 422  # other material
    rejected = recovery_record(chain)
    chain.client.post(
        f"{RECOVERY}/{rejected}/verify",
        json={"decision": "rejected", "notes": "wrong"},
        headers=chain.h["manager"],
    )
    assert link(rejected).status_code == 422
    good = recovery_record(chain)
    assert link(good).status_code == 200
    other = new(chain).json()["id"]
    clash = chain.client.post(
        f"{BASE}/{other}/recovery",
        json={"recovery_record_id": good},
        headers=chain.h["facility_operator"],
    )
    assert clash.status_code == 409
    assert (
        chain.client.post(
            f"{BASE}/{pid}/recovery", json={}, headers=chain.h["facility_operator"]
        ).status_code
        == 422
    )


def test_list_filters(chain: Chain) -> None:  # noqa: F811
    first = new(chain).json()
    second = new(
        chain,
        material_category_id=chain.category("glass"),
        weight_kg="5",
        current_facility_id=chain.facility("B"),
    ).json()
    m = chain.h["manager"]

    def ids(**params: str) -> set[str]:
        return {p["id"] for p in chain.client.get(BASE, params=params, headers=m).json()["items"]}

    assert ids() == {first["id"], second["id"]}
    assert ids(material_category_id=chain.category("glass")) == {second["id"]}
    assert ids(facility_id=chain.facility("A")) == {first["id"]}
    assert ids(status="recovered") == set()
    assert ids(q=first["passport_code"][3:8].lower()) == {first["id"]}
    assert ids(q="%") == set()
    ordered = chain.client.get(
        BASE, params={"sort_by": "weight_kg", "order": "asc"}, headers=m
    ).json()["items"]
    assert [p["id"] for p in ordered] == [second["id"], first["id"]]


def test_custody_history_is_append_only_in_the_database(chain: Chain) -> None:  # noqa: F811
    a = chain.facility("A")
    pid = new(chain).json()["id"]
    event(chain, pid, "received", to_facility_id=a)
    for statement in (
        "update custody_events set notes = 'tampered'",
        "delete from custody_events",
        "delete from material_passports",  # would cascade into custody_events
    ):
        with pytest.raises(DBAPIError, match="append-only"), chain.engine.begin() as conn:
            conn.execute(text(statement))
    assert count(chain.engine, "select count(*) from custody_events") == 2


def test_integrity_check_detects_a_tampered_chain(chain: Chain) -> None:  # noqa: F811
    a = chain.facility("A")
    pid = new(chain).json()["id"]
    event(chain, pid, "received", to_facility_id=a)
    event(chain, pid, "processed")
    with chain.engine.begin() as conn:  # an owner deliberately bypasses the guard
        conn.execute(text("alter table custody_events disable trigger custody_events_append_only"))
        conn.execute(text("update custody_events set event_type = 'verified' where sequence = 2"))
        conn.execute(text("update custody_events set sequence = 5 where sequence = 3"))
        conn.execute(text("alter table custody_events enable trigger custody_events_append_only"))
    check = chain.client.get(f"{BASE}/{pid}/integrity", headers=chain.h["manager"]).json()
    assert check["valid"] is False
    joined = " ".join(check["problems"])
    assert "sequence gap" in joined and "cannot follow" in joined
