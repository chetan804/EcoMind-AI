"""Recovery records: validation, separation of duties, verified-only metrics."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from tests.fixtures.chain import Chain, chain  # noqa: F401 (fixture)
from tests.fixtures.series import count

BASE = "/api/v1/circular-economy/recovery-records"
NOW = dt.datetime.now(dt.UTC)


def body(c: Chain, **over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "facility_id": c.facility(),
        "material_category_id": c.category("plastic"),
        "recovery_method": "recycled",
        "input_weight_kg": "100.000",
        "recovered_weight_kg": "80.500",
        "processed_at": (NOW - dt.timedelta(hours=2)).isoformat(),
    }
    data.update(over)
    return data


def create(c: Chain, who: str = "facility_operator", **over: Any) -> Any:
    payload = body(c, **over)
    return c.client.post(BASE, json=payload, headers=c.h[who])


def test_permissions(chain: Chain) -> None:  # noqa: F811
    assert chain.client.get(BASE).status_code == 401
    for who in ("citizen", "collector"):
        assert chain.client.get(BASE, headers=chain.h[who]).status_code == 403
        assert create(chain, who).status_code == 403
    assert chain.client.get(BASE, headers=chain.h["facility_operator"]).status_code == 200
    created = create(chain).json()
    verify = {"decision": "verified"}
    # operators record but cannot verify (no circular_economy:verify)
    op = chain.client.post(
        f"{BASE}/{created['id']}/verify", json=verify, headers=chain.h["facility_operator"]
    )
    assert op.status_code == 403 and op.json()["error"]["code"] == "forbidden"


def test_create_persists_a_pending_record(chain: Chain) -> None:  # noqa: F811
    response = create(chain)
    assert response.status_code == 201, response.text
    rec = response.json()
    assert rec["verification_status"] == "pending"
    assert rec["verified_by_id"] is None and rec["verified_at"] is None
    assert rec["created_by_id"] == str(chain.ids["facility_operator"])
    assert Decimal(rec["recovered_weight_kg"]) == Decimal("80.5")
    fetched = chain.client.get(f"{BASE}/{rec['id']}", headers=chain.h["manager"]).json()
    assert fetched == rec
    assert chain.client.get(f"{BASE}/{uuid.uuid4()}", headers=chain.h["manager"]).status_code == 404


def test_validation(chain: Chain) -> None:  # noqa: F811
    future = (NOW + dt.timedelta(hours=1)).isoformat()
    cases = {
        "recovered > input": {"recovered_weight_kg": "100.001"},
        "zero input": {"input_weight_kg": "0", "recovered_weight_kg": "0"},
        "negative recovered": {"recovered_weight_kg": "-1"},
        "future processed_at": {"processed_at": future},
        "naive processed_at": {"processed_at": "2026-01-01T10:00:00"},
        "unknown facility": {"facility_id": str(uuid.uuid4())},
        "unknown category": {"material_category_id": str(uuid.uuid4())},
        "bad method": {"recovery_method": "burned"},
        "extra field": {"verification_status": "verified"},
        "unknown task": {"collection_task_id": str(uuid.uuid4())},
    }
    for label, over in cases.items():
        assert create(chain, **over).status_code == 422, label
    inactive = chain.facility("CLOSED", status="inactive")
    assert create(chain, facility_id=inactive).status_code == 422
    # the recovery may reference a completed task, but not a pending one
    pending = chain.client.post(
        "/api/v1/collection/tasks",
        json={"title": "Not done", "address_text": "1 Road"},
        headers=chain.h["manager"],
    ).json()["id"]
    assert create(chain, collection_task_id=pending).status_code == 422
    done = chain.completed_task()
    assert create(chain, collection_task_id=done).status_code == 201
    # a client cannot pre-verify: the extra field was rejected above, and the default stays pending
    assert chain.client.get(BASE, headers=chain.h["manager"]).json()["total"] == 1


def test_verification_rules_and_audit(chain: Chain) -> None:  # noqa: F811
    rec = create(chain).json()
    url = f"{BASE}/{rec['id']}/verify"
    manager = chain.h["manager"]
    assert chain.client.post(url, json={"decision": "maybe"}, headers=manager).status_code == 422
    assert chain.client.post(url, json={"decision": "rejected"}, headers=manager).status_code == 422
    # the author cannot verify their own record, even when they hold the permission
    own = create(chain, "manager").json()
    self_try = chain.client.post(
        f"{BASE}/{own['id']}/verify", json={"decision": "verified"}, headers=manager
    )
    assert (
        self_try.status_code == 403
        and self_try.json()["error"]["code"] == "self_verification_forbidden"
    )
    ok = chain.client.post(
        url, json={"decision": "verified", "notes": "weighed twice"}, headers=manager
    )
    assert ok.status_code == 200
    out = ok.json()
    assert out["verification_status"] == "verified"
    assert out["verified_by_id"] == str(chain.ids["manager"]) and out["verified_at"]
    again = chain.client.post(
        url, json={"decision": "rejected", "notes": "changed my mind"}, headers=manager
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "recovery_already_decided"
    assert (
        chain.client.post(
            f"{BASE}/{uuid.uuid4()}/verify", json={"decision": "verified"}, headers=manager
        ).status_code
        == 404
    )
    assert (
        count(
            chain.engine, "select count(*) from audit_logs where action = 'recovery_record.created'"
        )
        == 2
    )
    assert (
        count(
            chain.engine,
            "select count(*) from audit_logs where action = 'recovery_record.verified'",
        )
        == 1
    )


def test_summary_counts_verified_records_only(chain: Chain) -> None:  # noqa: F811
    manager = chain.h["manager"]
    empty = chain.client.get(f"{BASE}/summary", headers=manager).json()
    assert empty["verified_records"] == 0 and empty["recovery_rate"] is None
    assert empty["by_category"] == [] and "not a landfill-diversion" in empty["basis"]

    plastic, glass = chain.category("plastic"), chain.category("glass")
    a = create(chain, input_weight_kg="100", recovered_weight_kg="80").json()
    b = create(
        chain,
        material_category_id=glass,
        input_weight_kg="50",
        recovered_weight_kg="25",
        recovery_method="reused",
    ).json()
    c = create(chain, input_weight_kg="1000", recovered_weight_kg="900").json()  # never verified
    d = create(chain, input_weight_kg="500", recovered_weight_kg="500").json()  # rejected
    for rec in (a, b):
        chain.client.post(
            f"{BASE}/{rec['id']}/verify", json={"decision": "verified"}, headers=manager
        )
    chain.client.post(
        f"{BASE}/{d['id']}/verify",
        json={"decision": "rejected", "notes": "bad scale"},
        headers=manager,
    )
    del c

    s = chain.client.get(f"{BASE}/summary", headers=manager).json()
    assert s["verified_records"] == 2 and s["pending_records"] == 1 and s["rejected_records"] == 1
    assert Decimal(s["input_weight_kg"]) == 150 and Decimal(s["recovered_weight_kg"]) == 105
    assert Decimal(s["recovery_rate"]) == Decimal("0.7000")
    by_cat = {x["key"]: x for x in s["by_category"]}
    assert set(by_cat) == {"plastic", "glass"}
    assert Decimal(by_cat["plastic"]["recovery_rate"]) == Decimal("0.8000")
    assert Decimal(by_cat["glass"]["recovery_rate"]) == Decimal("0.5000")
    assert {x["key"] for x in s["by_method"]} == {"recycled", "reused"}
    # filters: another facility has nothing; a future window has nothing
    other = chain.client.get(
        f"{BASE}/summary", params={"facility_id": str(uuid.uuid4())}, headers=manager
    ).json()
    assert other["verified_records"] == 0 and other["pending_records"] == 0
    window = chain.client.get(
        f"{BASE}/summary",
        params={"date_from": (NOW + dt.timedelta(days=2)).date().isoformat()},
        headers=manager,
    ).json()
    assert window["verified_records"] == 0
    del plastic


def test_list_filters_and_sorting(chain: Chain) -> None:  # noqa: F811
    manager = chain.h["manager"]
    small = create(chain, input_weight_kg="10", recovered_weight_kg="1").json()
    big = create(
        chain, input_weight_kg="900", recovered_weight_kg="5", recovery_method="composted"
    ).json()
    chain.client.post(f"{BASE}/{big['id']}/verify", json={"decision": "verified"}, headers=manager)

    def ids(**params: str) -> list[str]:
        page = chain.client.get(BASE, params=params, headers=manager).json()
        return [r["id"] for r in page["items"]]

    assert ids(status="verified") == [big["id"]]
    assert ids(status="pending") == [small["id"]]
    assert ids(recovery_method="composted") == [big["id"]]
    assert ids(sort_by="input_weight_kg", order="asc") == [small["id"], big["id"]]
    assert ids(sort_by="input_weight_kg", order="desc") == [big["id"], small["id"]]
    assert ids(material_category_id=chain.category("glass")) == []
    assert chain.client.get(BASE, params={"status": "nope"}, headers=manager).status_code == 422
