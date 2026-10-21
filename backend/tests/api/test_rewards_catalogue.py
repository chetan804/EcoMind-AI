"""Reward catalogue and redemptions: staff-entered items, spending, hand-over, cancellation."""

from __future__ import annotations

import datetime as dt
import re
import threading
import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.fixtures.api import bearer, create_user, login
from tests.fixtures.chain import Chain, chain  # noqa: F401 (fixture)
from tests.fixtures.series import count

BASE = "/api/v1/rewards"
CODE_PATTERN = r"^[A-HJ-KM-NP-Z2-9]{5}-[A-HJ-KM-NP-Z2-9]{5}$"


def fund(c: Chain, points: int) -> None:
    response = c.client.post(
        f"{BASE}/adjustments",
        json={"user_id": str(c.ids["citizen"]), "points": points, "description": "Test funding"},
        headers=c.h["manager"],
    )
    assert response.status_code == 201, response.text


def balance(c: Chain) -> int:
    return int(c.client.get(f"{BASE}/me/balance", headers=c.h["citizen"]).json()["points"])


def new_item(c: Chain, **over: Any) -> dict[str, Any]:
    body = {"name": "Reusable bottle", "points_cost": 100} | over
    response = c.client.post(f"{BASE}/items", json=body, headers=c.h["manager"])
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def redeem(c: Chain, item_id: str, request_id: str | None = None, who: str = "citizen") -> Any:
    return c.client.post(
        f"{BASE}/catalog/{item_id}/redeem",
        json={"client_request_id": request_id or str(uuid.uuid4())},
        headers=c.h[who],
    )


def stock_of(c: Chain, item_id: str) -> int | None:
    items = c.client.get(f"{BASE}/items", headers=c.h["manager"]).json()["items"]
    return next(i["stock"] for i in items if i["id"] == item_id)  # type: ignore[no-any-return]


def test_permissions(chain: Chain) -> None:  # noqa: F811
    item = new_item(chain)
    assert chain.client.get(f"{BASE}/catalog").status_code == 401
    for who in ("collector", "facility_operator"):  # they do not earn, so they cannot spend
        assert chain.client.get(f"{BASE}/catalog", headers=chain.h[who]).status_code == 403
        assert redeem(chain, item["id"], who=who).status_code == 403
    # Staff run the catalogue; they hold no points and cannot redeem on someone's behalf.
    assert redeem(chain, item["id"], who="manager").status_code == 403
    for method, path in (
        ("get", "/items"),
        ("post", "/items"),
        ("get", "/redemptions"),
    ):
        response = getattr(chain.client, method)(
            BASE + path, headers=chain.h["citizen"], **({"json": {}} if method == "post" else {})
        )
        assert response.status_code == 403, path
    assert (
        chain.client.patch(
            f"{BASE}/items/{item['id']}", json={"points_cost": 1}, headers=chain.h["citizen"]
        ).status_code
        == 403
    )
    fake = str(uuid.uuid4())
    assert (
        chain.client.post(
            f"{BASE}/redemptions/{fake}/fulfil", json={}, headers=chain.h["citizen"]
        ).status_code
        == 403
    )
    broke = redeem(chain, item["id"], who="administrator")  # allowed to redeem, holds no points
    assert broke.status_code == 409 and broke.json()["error"]["code"] == "insufficient_balance"


def test_the_platform_ships_no_catalogue(chain: Chain) -> None:  # noqa: F811
    assert chain.client.get(f"{BASE}/catalog", headers=chain.h["citizen"]).json()["total"] == 0
    assert chain.client.get(f"{BASE}/items", headers=chain.h["manager"]).json()["total"] == 0


def test_item_management_is_validated_and_audited(chain: Chain) -> None:  # noqa: F811
    bad: list[dict[str, Any]] = [
        {"name": "ab", "points_cost": 10},
        {"name": "Valid name", "points_cost": 0},
        {"name": "Valid name", "points_cost": 1_000_001},
        {"name": "Valid name", "points_cost": 10, "stock": -1},
        {"name": "Valid name", "points_cost": 10, "max_per_user": 0},
        {"name": "Valid name", "points_cost": 10, "valid_until": "2030-01-01T00:00:00"},
        {"name": "Valid name", "points_cost": 10, "extra": 1},
    ]
    for body in bad:
        response = chain.client.post(f"{BASE}/items", json=body, headers=chain.h["manager"])
        assert response.status_code == 422, body
    item = new_item(chain, description="  500 ml, steel  ", stock=5, max_per_user=2)
    assert item["description"] == "500 ml, steel" and item["active"] is True
    assert item["redeemed_count"] == 0 and item["pending_count"] == 0

    url = f"{BASE}/items/{item['id']}"
    for body in ({"name": None}, {"points_cost": None}, {"active": None}, {"points_cost": 0}):
        assert chain.client.patch(url, json=body, headers=chain.h["manager"]).status_code == 422
    changed = chain.client.patch(
        url,
        json={"points_cost": 150, "stock": None, "max_per_user": None},
        headers=chain.h["manager"],
    ).json()
    assert changed["points_cost"] == 150 and changed["stock"] is None
    assert changed["max_per_user"] is None and changed["name"] == "Reusable bottle"
    unchanged = chain.client.patch(url, json={"points_cost": 150}, headers=chain.h["manager"])
    assert unchanged.status_code == 200
    missing = chain.client.patch(
        f"{BASE}/items/{uuid.uuid4()}", json={"active": False}, headers=chain.h["manager"]
    )
    assert missing.status_code == 404
    assert (
        count(chain.engine, "select count(*) from audit_logs where action='reward_item.created'")
        == 1
    )
    # The no-op patch wrote no audit row.
    assert (
        count(chain.engine, "select count(*) from audit_logs where action='reward_item.updated'")
        == 1
    )
    inactive = chain.client.get(
        f"{BASE}/items", params={"active": False}, headers=chain.h["manager"]
    )
    assert inactive.json()["total"] == 0


def test_the_catalogue_shows_only_what_can_be_redeemed(chain: Chain) -> None:  # noqa: F811
    live = new_item(chain, name="Live item", points_cost=10)
    new_item(chain, name="Switched off", points_cost=20, active=False)
    soon = (dt.datetime.now(dt.UTC) + dt.timedelta(days=3)).isoformat()
    new_item(chain, name="Ends soon", points_cost=30, valid_until=soon)
    expired = new_item(chain, name="Already over", points_cost=40)
    with chain.engine.begin() as conn:
        conn.execute(
            text("update reward_items set valid_until = now() - interval '1 hour' where id = :i"),
            {"i": expired["id"]},
        )
    gone = new_item(chain, name="Sold out", points_cost=50, stock=0)
    limited = new_item(chain, name="Limited to one", points_cost=5, max_per_user=1)
    fund(chain, 100)
    assert redeem(chain, limited["id"]).status_code == 201

    page = chain.client.get(f"{BASE}/catalog", headers=chain.h["citizen"]).json()
    by_name = {i["name"]: i for i in page["items"]}
    assert list(by_name) == ["Limited to one", "Live item", "Ends soon", "Sold out"]  # by cost
    assert by_name["Live item"]["available"] is True
    assert by_name["Live item"]["remaining_for_you"] is None
    assert by_name["Sold out"]["unavailable_reason"] == "out_of_stock"
    assert by_name["Sold out"]["id"] == gone["id"]
    assert by_name["Limited to one"]["unavailable_reason"] == "limit_reached"
    assert by_name["Limited to one"]["remaining_for_you"] == 0
    assert "created_by_id" not in by_name["Live item"] and "active" not in by_name["Live item"]
    assert live["id"] == by_name["Live item"]["id"]


def test_redeeming_spends_points_and_leaves_a_trail(chain: Chain) -> None:  # noqa: F811
    item = new_item(chain, stock=3, points_cost=120)
    fund(chain, 300)
    key = str(uuid.uuid4())
    first = redeem(chain, item["id"], key)
    assert first.status_code == 201, first.text
    red = first.json()
    assert red["status"] == "pending" and red["points_spent"] == 120
    assert red["item_name"] == "Reusable bottle" and red["user_name"] is None
    assert red["user_email"] is None
    assert re.match(CODE_PATTERN, red["code"])
    assert balance(chain) == 180 and stock_of(chain, item["id"]) == 2

    entries = chain.client.get(f"{BASE}/me/entries", headers=chain.h["citizen"]).json()["items"]
    spend = next(e for e in entries if e["entry_type"] == "redeemed")
    assert spend["points"] == -120 and spend["source_type"] == "reward_redemption"
    assert spend["source_id"] == red["id"] and spend["impact_weight_kg"] is None
    summary = chain.client.get(f"{BASE}/me/balance", headers=chain.h["citizen"]).json()
    assert summary["earned_points"] == 0  # spending is not earning

    # The same request id again: the same redemption, nothing more is spent.
    again = redeem(chain, item["id"], key)
    assert again.status_code == 200 and again.json()["id"] == red["id"]
    assert again.json()["code"] == red["code"]
    assert balance(chain) == 180 and stock_of(chain, item["id"]) == 2
    # A request id may not be recycled for another reward.
    other = new_item(chain, name="Tote bag")
    reused = redeem(chain, other["id"], key)
    assert (
        reused.status_code == 409 and reused.json()["error"]["code"] == "client_request_id_reused"
    )
    # A different request id is a new purchase.
    assert redeem(chain, item["id"]).status_code == 201 and balance(chain) == 60

    mine = chain.client.get(f"{BASE}/me/redemptions", headers=chain.h["citizen"]).json()
    assert mine["total"] == 2
    assert (
        count(chain.engine, "select count(*) from audit_logs where action='reward.redeemed'") == 2
    )
    notes = chain.client.get("/api/v1/notifications", headers=chain.h["citizen"]).json()["items"]
    assert any(red["code"] in n["body"] and n["title"] == "Reward redeemed" for n in notes)


def test_a_redemption_that_is_refused_changes_nothing(chain: Chain) -> None:  # noqa: F811
    item = new_item(chain, points_cost=100, stock=1, max_per_user=1)
    dear = new_item(chain, name="Too dear", points_cost=900)
    off = new_item(chain, name="Switched off", active=False)
    old = new_item(chain, name="Over and done")
    with chain.engine.begin() as conn:
        conn.execute(
            text("update reward_items set valid_until = now() - interval '1 second' where id=:i"),
            {"i": old["id"]},
        )
    fund(chain, 250)

    poor = redeem(chain, dear["id"])
    assert poor.status_code == 409 and poor.json()["error"]["code"] == "insufficient_balance"
    assert redeem(chain, off["id"]).status_code == 404
    assert redeem(chain, old["id"]).status_code == 404
    assert redeem(chain, str(uuid.uuid4())).status_code == 404
    assert balance(chain) == 250

    assert redeem(chain, item["id"]).status_code == 201
    limit = redeem(chain, item["id"])
    # Stock is now 0 as well; the stock check comes first, so make it a pure limit case:
    assert limit.status_code == 409 and limit.json()["error"]["code"] == "reward_unavailable"
    chain.client.patch(f"{BASE}/items/{item['id']}", json={"stock": 10}, headers=chain.h["manager"])
    limit = redeem(chain, item["id"])
    assert limit.status_code == 409 and limit.json()["error"]["code"] == "redemption_limit_reached"
    assert balance(chain) == 150
    assert count(chain.engine, "select count(*) from reward_redemptions") == 1
    assert count(chain.engine, "select count(*) from reward_ledger_entries where points < 0") == 1
    bad = chain.client.post(
        f"{BASE}/catalog/{item['id']}/redeem", json={}, headers=chain.h["citizen"]
    )
    assert bad.status_code == 422
    bad = chain.client.post(
        f"{BASE}/catalog/{item['id']}/redeem",
        json={"client_request_id": "not-a-uuid"},
        headers=chain.h["citizen"],
    )
    assert bad.status_code == 422


def test_cancelling_returns_points_and_stock_exactly_once(chain: Chain) -> None:  # noqa: F811
    item = new_item(chain, stock=2, points_cost=100, max_per_user=1)
    fund(chain, 100)
    red = redeem(chain, item["id"]).json()
    assert balance(chain) == 0 and stock_of(chain, item["id"]) == 1

    stranger = chain.client.post(
        f"{BASE}/me/redemptions/{red['id']}/cancel", json={}, headers=chain.h["administrator"]
    )
    assert stranger.status_code == 404  # someone else's redemption does not exist for you
    assert (
        chain.client.post(
            f"{BASE}/me/redemptions/{uuid.uuid4()}/cancel", json={}, headers=chain.h["citizen"]
        ).status_code
        == 404
    )
    done = chain.client.post(
        f"{BASE}/me/redemptions/{red['id']}/cancel",
        json={"reason": "Changed my mind"},
        headers=chain.h["citizen"],
    )
    assert done.status_code == 200, done.text
    assert (
        done.json()["status"] == "cancelled" and done.json()["cancel_reason"] == "Changed my mind"
    )
    assert balance(chain) == 100 and stock_of(chain, item["id"]) == 2

    entries = chain.client.get(f"{BASE}/me/entries", headers=chain.h["citizen"]).json()["items"]
    spend = next(e for e in entries if e["entry_type"] == "redeemed")
    refund = next(e for e in entries if e["entry_type"] == "reversal")
    assert refund["points"] == 100 and refund["reverses_entry_id"] == spend["id"]
    assert refund["source_id"] == red["id"] and refund["impact_weight_kg"] is None

    # Final: no second refund, no fulfilment of a cancelled redemption.
    again = chain.client.post(
        f"{BASE}/me/redemptions/{red['id']}/cancel", json={}, headers=chain.h["citizen"]
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "invalid_redemption_state"
    assert (
        chain.client.post(
            f"{BASE}/redemptions/{red['id']}/fulfil", json={}, headers=chain.h["manager"]
        ).status_code
        == 409
    )
    assert balance(chain) == 100
    # A cancelled redemption no longer counts toward the per-person limit.
    assert redeem(chain, item["id"]).status_code == 201
    assert (
        count(
            chain.engine,
            "select count(*) from audit_logs where action='reward.redemption_cancelled'",
        )
        == 1
    )


def test_staff_fulfil_and_cancel_workflow(chain: Chain) -> None:  # noqa: F811
    item = new_item(chain, points_cost=40, stock=5)
    fund(chain, 200)
    first = redeem(chain, item["id"]).json()
    second = redeem(chain, item["id"]).json()
    third = redeem(chain, item["id"]).json()

    listing = chain.client.get(f"{BASE}/redemptions", headers=chain.h["manager"]).json()
    assert listing["total"] == 3
    row = listing["items"][0]
    assert row["user_email"] == "citizen@example.org" and row["user_name"]
    pending = chain.client.get(
        f"{BASE}/redemptions", params={"status": "pending"}, headers=chain.h["manager"]
    )
    assert pending.json()["total"] == 3
    by_code = chain.client.get(
        f"{BASE}/redemptions", params={"code": first["code"].lower()}, headers=chain.h["manager"]
    ).json()
    assert [r["id"] for r in by_code["items"]] == [first["id"]]
    by_user = chain.client.get(
        f"{BASE}/redemptions",
        params={"user_id": str(uuid.uuid4())},
        headers=chain.h["manager"],
    )
    assert by_user.json()["total"] == 0
    assert (
        chain.client.get(
            f"{BASE}/redemptions", params={"status": "bogus"}, headers=chain.h["manager"]
        ).status_code
        == 422
    )
    shown = chain.client.get(f"{BASE}/items", headers=chain.h["manager"]).json()["items"][0]
    assert shown["pending_count"] == 3 and shown["redeemed_count"] == 3

    ok = chain.client.post(
        f"{BASE}/redemptions/{first['id']}/fulfil",
        json={"note": "Handed over at the depot"},
        headers=chain.h["manager"],
    )
    assert ok.status_code == 200 and ok.json()["status"] == "fulfilled"
    assert ok.json()["note"] == "Handed over at the depot" and ok.json()["fulfilled_at"]
    # Fulfilment (note optional, body optional) works once only.
    assert (
        chain.client.post(
            f"{BASE}/redemptions/{first['id']}/fulfil", json={}, headers=chain.h["manager"]
        ).status_code
        == 409
    )
    bodyless = chain.client.post(
        f"{BASE}/redemptions/{second['id']}/fulfil", headers=chain.h["manager"]
    )
    assert bodyless.status_code == 200

    # A handed-over reward can be neither cancelled by the owner nor by staff.
    for url, body in (
        (f"{BASE}/me/redemptions/{first['id']}/cancel", {}),
        (f"{BASE}/redemptions/{first['id']}/cancel", {"reason": "Too late"}),
    ):
        who = "citizen" if "/me/" in url else "manager"
        refused = chain.client.post(url, json=body, headers=chain.h[who])
        assert refused.status_code == 409, url

    needs_reason = chain.client.post(
        f"{BASE}/redemptions/{third['id']}/cancel", json={}, headers=chain.h["manager"]
    )
    assert needs_reason.status_code == 422
    cancelled = chain.client.post(
        f"{BASE}/redemptions/{third['id']}/cancel",
        json={"reason": "Item recalled by supplier"},
        headers=chain.h["manager"],
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert balance(chain) == 200 - 80 and stock_of(chain, item["id"]) == 5 - 3 + 1

    titles = [
        n["title"]
        for n in chain.client.get("/api/v1/notifications", headers=chain.h["citizen"]).json()[
            "items"
        ]
    ]
    assert "Your reward was handed over" in titles
    assert "Your reward redemption was cancelled" in titles
    for action in ("reward.redemption_fulfilled", "reward.redemption_cancelled"):
        assert count(chain.engine, f"select count(*) from audit_logs where action='{action}'") >= 1


def test_a_redemption_cannot_be_reversed_through_the_adjustment_endpoint(
    chain: Chain,  # noqa: F811
) -> None:
    item = new_item(chain, points_cost=10)
    fund(chain, 10)
    redeem(chain, item["id"])
    entries = chain.client.get(f"{BASE}/me/entries", headers=chain.h["citizen"]).json()["items"]
    spend = next(e for e in entries if e["entry_type"] == "redeemed")
    response = chain.client.post(
        f"{BASE}/entries/{spend['id']}/reverse",
        json={"reason": "Trying to dodge the workflow"},
        headers=chain.h["manager"],
    )
    assert response.status_code == 422
    assert balance(chain) == 0


def _race(*calls: Any) -> list[Any]:
    results: list[Any] = []
    barrier = threading.Barrier(len(calls))

    def attempt(call: Any) -> None:
        barrier.wait()
        results.append(call())

    threads = [threading.Thread(target=attempt, args=(call,)) for call in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def test_two_simultaneous_requests_cannot_overspend_the_balance(chain: Chain) -> None:  # noqa: F811
    # Different items, so only the per-user lock stops both from reading the same balance.
    first = new_item(chain, name="First reward", points_cost=100)
    second = new_item(chain, name="Second reward", points_cost=100)
    fund(chain, 100)
    results = _race(lambda: redeem(chain, first["id"]), lambda: redeem(chain, second["id"]))
    assert sorted(r.status_code for r in results) == [201, 409]
    assert balance(chain) == 0
    assert count(chain.engine, "select count(*) from reward_redemptions") == 1


def test_simultaneous_requests_cannot_oversell_the_last_unit(chain: Chain) -> None:  # noqa: F811
    # Several people, one unit: only the item lock stops them all from seeing stock = 1.
    item = new_item(chain, points_cost=10, stock=1)
    fund(chain, 100)
    tokens = [chain.h["citizen"]]
    for n in range(5):
        email = f"buyer{n}@example.org"
        buyer = create_user(chain.engine, email=email, roles=("citizen",))
        granted = chain.client.post(
            f"{BASE}/adjustments",
            json={"user_id": str(buyer), "points": 100, "description": "Test funding"},
            headers=chain.h["manager"],
        )
        assert granted.status_code == 201
        tokens.append(bearer(login(chain.client, email)["access_token"]))

    def buy(headers: dict[str, str]) -> Any:
        return chain.client.post(
            f"{BASE}/catalog/{item['id']}/redeem",
            json={"client_request_id": str(uuid.uuid4())},
            headers=headers,
        )

    results = _race(*[lambda h=h: buy(h) for h in tokens])
    assert sorted(r.status_code for r in results) == [201, 409, 409, 409, 409, 409]
    assert stock_of(chain, item["id"]) == 0
    assert count(chain.engine, "select count(*) from reward_redemptions") == 1


def test_the_same_request_id_sent_twice_at_once_spends_once(chain: Chain) -> None:  # noqa: F811
    item = new_item(chain, points_cost=10)
    fund(chain, 100)
    key = str(uuid.uuid4())
    results: list[Any] = []
    barrier = threading.Barrier(2)

    def attempt() -> None:
        barrier.wait()
        results.append(redeem(chain, item["id"], key))

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(r.status_code for r in results) == [200, 201]
    assert results[0].json()["id"] == results[1].json()["id"]
    assert balance(chain) == 90


def test_the_database_enforces_the_redemption_rules(chain: Chain) -> None:  # noqa: F811
    item = new_item(chain, points_cost=10)
    fund(chain, 10)
    red = redeem(chain, item["id"]).json()
    statements = (
        "update reward_items set stock = -1",
        "update reward_items set points_cost = 0",
        "update reward_redemptions set status = 'fulfilled'",  # no fulfilled_at
        "update reward_redemptions set status = 'cancelled', cancelled_at = now()",  # no refund
        "update reward_redemptions set points_spent = 0",
    )
    for statement in statements:
        with pytest.raises(DBAPIError), chain.engine.begin() as conn:
            conn.execute(text(statement))
    duplicate = (
        "insert into reward_redemptions (user_id, item_id, item_name, points_spent, code, "
        "client_request_id, ledger_entry_id) "
        "select user_id, item_id, item_name, points_spent, code, gen_random_uuid(), ledger_entry_id "
        "from reward_redemptions where id = :i"
    )
    with pytest.raises(DBAPIError), chain.engine.begin() as conn:
        conn.execute(text(duplicate), {"i": red["id"]})
    assert balance(chain) == 0
