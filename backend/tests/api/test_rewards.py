"""Rewards ledger: earning, balances, adjustments, reversals, append-only guarantee."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.fixtures.chain import Chain, chain  # noqa: F401 (fixture)
from tests.fixtures.series import count

BASE = "/api/v1/rewards"
REPORTS = "/api/v1/waste-reports"


def earn(c: Chain, kg: str = "37.5") -> str:
    """Citizen reports, manager verifies, collector collects: returns the task id."""
    report = c.client.post(
        REPORTS,
        json={"title": "Pile of bottles", "latitude": "17.40", "longitude": "78.47"},
        headers=c.h["citizen"],
    )
    assert report.status_code == 201, report.text
    rid = report.json()["id"]
    verified = c.client.post(
        f"{REPORTS}/{rid}/review", json={"status": "verified"}, headers=c.h["manager"]
    )
    assert verified.status_code == 200, verified.text
    return c.completed_task(kg, report_id=rid)


def balance(c: Chain, who: str = "citizen") -> dict[str, Any]:
    response = c.client.get(f"{BASE}/me/balance", headers=c.h[who])
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def adjust(c: Chain, points: int, **over: Any) -> Any:
    body = {"user_id": str(c.ids["citizen"]), "points": points, "description": "Goodwill"} | over
    return c.client.post(f"{BASE}/adjustments", json=body, headers=c.h["manager"])


def test_permissions(chain: Chain) -> None:  # noqa: F811
    assert chain.client.get(f"{BASE}/me/balance").status_code == 401
    for who in ("collector", "facility_operator"):  # they do not earn rewards
        assert chain.client.get(f"{BASE}/me/balance", headers=chain.h[who]).status_code == 403
    for path in ("/ledger", "/ledger/summary"):
        assert chain.client.get(BASE + path, headers=chain.h["citizen"]).status_code == 403
        assert chain.client.get(BASE + path, headers=chain.h["manager"]).status_code == 200
    assert (
        adjust(
            chain,
            10,
        ).status_code
        == 201
    )
    forged = chain.client.post(
        f"{BASE}/adjustments",
        json={"user_id": str(chain.ids["citizen"]), "points": 5000, "description": "mine"},
        headers=chain.h["citizen"],
    )
    assert forged.status_code == 403


def test_empty_balance_and_earning_from_a_verified_collection(chain: Chain) -> None:  # noqa: F811
    zero = balance(chain)
    assert zero["points"] == 0 and zero["entries"] == 0 and Decimal(zero["impact_weight_kg"]) == 0
    assert zero["points_per_kg"] == 10 and "no carbon" in zero["basis"]
    task_id = earn(chain)
    b = balance(chain)
    assert b["points"] == 375 and b["earned_points"] == 375 and b["entries"] == 1
    assert Decimal(b["impact_weight_kg"]) == Decimal("37.5")
    entries = chain.client.get(f"{BASE}/me/entries", headers=chain.h["citizen"]).json()
    assert entries["total"] == 1
    entry = entries["items"][0]
    assert entry["entry_type"] == "earned" and entry["source_type"] == "collection_task"
    assert entry["source_id"] == task_id and entry["user_id"] == str(chain.ids["citizen"])
    only = chain.client.get(
        f"{BASE}/me/entries", params={"entry_type": "reversal"}, headers=chain.h["citizen"]
    )
    assert only.json()["total"] == 0


def test_a_task_without_a_verified_report_earns_nothing(chain: Chain) -> None:  # noqa: F811
    chain.completed_task("20")  # a manager-created task has no reporter
    assert balance(chain)["points"] == 0
    assert chain.client.get(f"{BASE}/ledger", headers=chain.h["manager"]).json()["total"] == 0


def test_entries_are_private_to_their_owner(chain: Chain) -> None:  # noqa: F811
    earn(chain)
    other = chain.client.post(
        "/api/v1/auth/register",
        json={
            "email": "second@example.org",
            "password": "Str0ng-Passphrase-77!",
            "full_name": "Second Citizen",
        },
    )
    assert other.status_code == 201, other.text
    login = chain.client.post(
        "/api/v1/auth/login",
        json={"email": "second@example.org", "password": "Str0ng-Passphrase-77!"},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    assert chain.client.get(f"{BASE}/me/balance", headers=headers).json()["points"] == 0
    assert chain.client.get(f"{BASE}/me/entries", headers=headers).json()["total"] == 0


def test_adjustments(chain: Chain) -> None:  # noqa: F811
    earn(chain)
    assert adjust(chain, 50).status_code == 201
    assert balance(chain)["points"] == 425
    over = adjust(chain, -500)
    assert over.status_code == 409 and over.json()["error"]["code"] == "insufficient_balance"
    assert balance(chain)["points"] == 425  # nothing was written
    assert adjust(chain, -425).status_code == 201
    assert balance(chain)["points"] == 0
    bad = (
        adjust(chain, 0),
        adjust(chain, 100_001),
        adjust(chain, 5, description="x"),
        adjust(chain, 5, user_id=str(uuid.uuid4())),
        adjust(chain, 5, extra="field"),
    )
    assert [r.status_code for r in bad] == [422] * 5
    adjustment = chain.client.get(
        f"{BASE}/ledger", params={"entry_type": "adjustment"}, headers=chain.h["manager"]
    ).json()
    assert adjustment["total"] == 2
    assert all(
        e["source_type"] == "manual" and e["created_by_id"] == str(chain.ids["manager"])
        for e in adjustment["items"]
    )
    assert (
        count(chain.engine, "select count(*) from audit_logs where action = 'reward.adjusted'") == 2
    )
    assert (
        count(
            chain.engine,
            "select count(*) from notifications where title like 'Your reward balance%'",
        )
        == 2
    )


def test_reversal(chain: Chain) -> None:  # noqa: F811
    earn(chain)
    earned_id = chain.client.get(f"{BASE}/me/entries", headers=chain.h["citizen"]).json()["items"][
        0
    ]["id"]
    url = f"{BASE}/entries/{earned_id}/reverse"
    assert (
        chain.client.post(url, json={"reason": "no"}, headers=chain.h["manager"]).status_code == 422
    )
    assert (
        chain.client.post(
            url, json={"reason": "Weighed wrongly"}, headers=chain.h["citizen"]
        ).status_code
        == 403
    )
    ok = chain.client.post(url, json={"reason": "Weighed wrongly"}, headers=chain.h["manager"])
    assert ok.status_code == 201, ok.text
    rev = ok.json()
    assert (
        rev["entry_type"] == "reversal"
        and rev["points"] == -375
        and rev["reverses_entry_id"] == earned_id
    )
    b = balance(chain)
    assert b["points"] == 0 and b["earned_points"] == 375
    assert Decimal(b["impact_weight_kg"]) == 0  # the reversed weight no longer counts
    again = chain.client.post(url, json={"reason": "Twice by mistake"}, headers=chain.h["manager"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "entry_already_reversed"
    assert (
        chain.client.post(
            f"{BASE}/entries/{rev['id']}/reverse",
            json={"reason": "reverse a reversal"},
            headers=chain.h["manager"],
        ).status_code
        == 422
    )
    assert (
        chain.client.post(
            f"{BASE}/entries/{uuid.uuid4()}/reverse",
            json={"reason": "Missing entry"},
            headers=chain.h["manager"],
        ).status_code
        == 404
    )
    # a positive adjustment can be reversed; a negative one (a debit) cannot
    bonus = adjust(chain, 5).json()["id"]
    assert (
        chain.client.post(
            f"{BASE}/entries/{bonus}/reverse",
            json={"reason": "Mistaken bonus"},
            headers=chain.h["manager"],
        ).status_code
        == 201
    )
    chain.client.post(
        f"{BASE}/adjustments",
        json={"user_id": str(chain.ids["citizen"]), "points": 100, "description": "Top up"},
        headers=chain.h["manager"],
    )
    debit = adjust(chain, -10).json()["id"]
    r = chain.client.post(
        f"{BASE}/entries/{debit}/reverse",
        json={"reason": "Undo the debit"},
        headers=chain.h["manager"],
    )
    assert r.status_code == 422


def test_ledger_summary_and_filters(chain: Chain) -> None:  # noqa: F811
    earn(chain, "10")
    adjust(chain, 30)
    adjust(chain, -20)
    s = chain.client.get(f"{BASE}/ledger/summary", headers=chain.h["manager"]).json()
    assert s["entries"] == 3 and s["users"] == 1
    assert s["points_issued"] == 130 and s["points_removed"] == 20 and s["net_points"] == 110
    assert Decimal(s["impact_weight_kg"]) == 10
    m = chain.h["manager"]
    mine = chain.client.get(
        f"{BASE}/ledger", params={"user_id": str(chain.ids["citizen"])}, headers=m
    )
    assert mine.json()["total"] == 3
    nobody = chain.client.get(f"{BASE}/ledger", params={"user_id": str(uuid.uuid4())}, headers=m)
    assert nobody.json()["total"] == 0
    src = chain.client.get(f"{BASE}/ledger", params={"source_type": "collection_task"}, headers=m)
    assert src.json()["total"] == 1


def test_ledger_is_append_only_in_the_database(chain: Chain) -> None:  # noqa: F811
    earn(chain)
    for statement in (
        "update reward_ledger_entries set points = 999999",
        "delete from reward_ledger_entries",
    ):
        with pytest.raises(DBAPIError, match="append-only"), chain.engine.begin() as conn:
            conn.execute(text(statement))
    assert balance(chain)["points"] == 375
