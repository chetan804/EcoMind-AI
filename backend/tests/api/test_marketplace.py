"""Marketplace: permissions, visibility, listing lifecycle, request rules, notifications, audit."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from tests.fixtures.api import ClientFactory, bearer, create_user, login
from tests.fixtures.series import count

BASE = "/api/v1/marketplace"
LISTINGS = f"{BASE}/listings"
NOTES = "/api/v1/notifications"


class Env:
    def __init__(self, client: TestClient, engine: Engine) -> None:
        self.client, self.engine = client, engine
        self.ids: dict[str, uuid.UUID] = {}
        self.h: dict[str, dict[str, str]] = {}
        for who, role in (
            ("citizen", "citizen"),
            ("other", "citizen"),
            ("collector", "collector"),
            ("operator", "facility_operator"),
            ("operator2", "facility_operator"),
            ("manager", "manager"),
        ):
            email = f"{who}@example.org"
            self.ids[who] = create_user(engine, email=email, roles=(role,))
            self.h[who] = bearer(login(client, email)["access_token"])

    def listing(self, who: str = "operator", publish: bool = True, **over: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "title": "Office chairs",
            "description": "Surplus from a floor move",
            "category": "furniture",
            "quantity": "30",
            "unit": "units",
            "condition": "good",
        }
        body.update(over)
        response = self.client.post(LISTINGS, json=body, headers=self.h[who])
        assert response.status_code == 201, response.text
        created: dict[str, Any] = response.json()
        if publish:
            return self.act(created["id"], "publish", who)
        return created

    def act(
        self, listing_id: str, action: str, who: str = "operator", **body: Any
    ) -> dict[str, Any]:
        response = self.client.post(
            f"{LISTINGS}/{listing_id}/{action}", json=body or None, headers=self.h[who]
        )
        assert response.status_code == 200, response.text
        out: dict[str, Any] = response.json()
        return out

    def ask(self, listing_id: str, who: str = "citizen", message: str | None = None) -> Any:
        return self.client.post(
            f"{LISTINGS}/{listing_id}/requests", json={"message": message}, headers=self.h[who]
        )

    def decide(self, request_id: str, action: str, who: str) -> Any:
        return self.client.post(f"{BASE}/requests/{request_id}/{action}", headers=self.h[who])

    def listing_status(self, listing_id: str, who: str = "manager") -> str:
        return str(
            self.client.get(f"{LISTINGS}/{listing_id}", headers=self.h[who]).json()["status"]
        )

    def notes(self, who: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = self.client.get(NOTES, headers=self.h[who]).json()["items"]
        return items

    def audits(self, action: str) -> int:
        return count(self.engine, "select count(*) from audit_logs where action=:a", a=action)


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    return Env(make_client(), db_engine)


def test_authentication_and_permissions(env: Env) -> None:
    some = uuid.uuid4()
    for method, url in (
        ("get", LISTINGS),
        ("post", LISTINGS),
        ("get", f"{LISTINGS}/{some}"),
        ("post", f"{LISTINGS}/{some}/requests"),
        ("get", f"{BASE}/requests/mine"),
        ("post", f"{BASE}/requests/{some}/accept"),
    ):
        assert env.client.request(method, url).status_code == 401, (method, url)
    body = {
        "title": "Pallets",
        "category": "wood",
        "quantity": "5",
        "unit": "units",
        "condition": "fair",
    }
    # everyone signed in can browse, but only operators and managers can offer material
    for who in ("citizen", "collector", "operator", "manager"):
        assert env.client.get(LISTINGS, headers=env.h[who]).status_code == 200
    for who in ("citizen", "collector"):
        assert env.client.post(LISTINGS, json=body, headers=env.h[who]).status_code == 403
    for who in ("operator", "manager"):
        assert env.client.post(LISTINGS, json=body, headers=env.h[who]).status_code == 201
    # operators cannot request (not in their grants? they can) - they hold marketplace:request
    assert env.client.get(f"{BASE}/requests/mine", headers=env.h["operator"]).status_code == 200


def test_create_makes_a_private_draft_and_audits(env: Env) -> None:
    draft = env.listing(publish=False)
    assert draft["status"] == "draft" and draft["is_mine"] is True
    assert draft["owner_id"] == str(env.ids["operator"]) and draft["published_at"] is None
    assert draft["quantity"] == "30.000" and draft["pending_request_count"] == 0
    # nobody else sees a draft, in the list or by id; the answer is the same as for a missing id
    for who in ("citizen", "operator2"):
        assert env.client.get(f"{LISTINGS}/{draft['id']}", headers=env.h[who]).status_code == 404
        assert env.client.get(LISTINGS, headers=env.h[who]).json()["total"] == 0
    # the owner and any manager do
    assert env.client.get(LISTINGS, headers=env.h["operator"]).json()["total"] == 1
    assert env.client.get(f"{LISTINGS}/{draft['id']}", headers=env.h["manager"]).status_code == 200
    assert env.audits("marketplace_listing.created") == 1


@pytest.mark.parametrize(
    "over",
    [
        {"title": "ab"},
        {"quantity": "0"},
        {"quantity": "-1"},
        {"quantity": "1.2345"},
        {"category": "gold"},
        {"unit": "tonnes"},
        {"condition": "mint"},
        {"facility_id": str(uuid.uuid4())},
        {"price": "10"},
    ],
)
def test_invalid_listings_are_rejected(env: Env, over: dict[str, Any]) -> None:
    body: dict[str, Any] = {
        "title": "Pallets",
        "category": "wood",
        "quantity": "5",
        "unit": "units",
        "condition": "fair",
    }
    body.update(over)
    response = env.client.post(LISTINGS, json=body, headers=env.h["operator"])
    assert response.status_code == 422, response.text


def test_listing_can_name_a_facility(env: Env) -> None:
    created = env.client.post(
        "/api/v1/facilities",
        json={"code": "MRF-1", "name": "North recovery depot", "facility_type": "depot"},
        headers=env.h["manager"],
    ).json()
    out = env.listing(facility_id=created["id"], pickup_city="Hyderabad")
    assert out["facility_name"] == "North recovery depot" and out["pickup_city"] == "Hyderabad"


def test_lifecycle_and_edit_rules(env: Env) -> None:
    draft = env.listing(publish=False)
    lid = draft["id"]
    # edit while draft
    patched = env.client.patch(
        f"{LISTINGS}/{lid}", json={"quantity": "25"}, headers=env.h["operator"]
    )
    assert patched.status_code == 200 and patched.json()["quantity"] == "25.000"
    assert (
        env.client.patch(
            f"{LISTINGS}/{lid}", json={"title": None}, headers=env.h["operator"]
        ).status_code
        == 422
    )
    # only the owner or a manager edits, and the caller cannot tell a draft exists
    assert (
        env.client.patch(
            f"{LISTINGS}/{lid}", json={"title": "Taken"}, headers=env.h["citizen"]
        ).status_code
        == 404
    )
    published = env.act(lid, "publish")
    assert published["status"] == "published" and published["published_at"] is not None
    # a listing is published once
    assert (
        env.client.post(f"{LISTINGS}/{lid}/publish", headers=env.h["operator"]).status_code == 409
    )
    # others now see it but still cannot edit or close it
    assert (
        env.client.get(f"{LISTINGS}/{lid}", headers=env.h["citizen"]).json()[
            "pending_request_count"
        ]
        is None
    )
    assert (
        env.client.patch(
            f"{LISTINGS}/{lid}", json={"title": "Mine now"}, headers=env.h["citizen"]
        ).status_code
        == 403
    )
    assert (
        env.client.post(f"{LISTINGS}/{lid}/close", json={}, headers=env.h["operator2"]).status_code
        == 403
    )
    # a manager can
    assert (
        env.client.patch(
            f"{LISTINGS}/{lid}", json={"condition": "fair"}, headers=env.h["manager"]
        ).json()["condition"]
        == "fair"
    )
    closed = env.act(lid, "close", reason="Collected by the owner")
    assert closed["status"] == "closed" and closed["close_reason"] == "Collected by the owner"
    assert closed["closed_at"] is not None
    # closed is final: no edit, publish or close
    assert (
        env.client.patch(
            f"{LISTINGS}/{lid}", json={"title": "Again"}, headers=env.h["operator"]
        ).status_code
        == 409
    )
    assert (
        env.client.post(f"{LISTINGS}/{lid}/publish", headers=env.h["operator"]).status_code == 409
    )
    assert (
        env.client.post(f"{LISTINGS}/{lid}/close", json={}, headers=env.h["operator"]).status_code
        == 409
    )
    # a no-op patch writes no audit entry
    before = env.audits("marketplace_listing.updated")
    pub = env.listing()
    env.client.patch(
        f"{LISTINGS}/{pub['id']}", json={"title": pub["title"]}, headers=env.h["operator"]
    )
    assert env.audits("marketplace_listing.updated") == before
    assert (
        env.audits("marketplace_listing.published") == 2
        and env.audits("marketplace_listing.closed") == 1
    )


def test_a_draft_can_be_closed_without_ever_being_published(env: Env) -> None:
    draft = env.listing(publish=False)
    closed = env.act(draft["id"], "close")
    assert closed["status"] == "closed" and closed["published_at"] is None


def test_requests_follow_the_rules(env: Env) -> None:
    lid = env.listing()["id"]
    draft = env.listing(publish=False)["id"]
    # the owner cannot ask for their own listing; a draft cannot be asked for
    assert env.ask(lid, "operator").status_code == 409
    assert env.ask(lid, "operator").json()["error"]["code"] == "own_listing"
    assert env.ask(draft, "citizen").status_code == 404
    first = env.ask(lid, "citizen", "We need chairs for a community hall")
    assert first.status_code == 201, first.text
    req = first.json()
    assert req["status"] == "pending" and req["decided_at"] is None
    assert req["requester_email"] == "citizen@example.org"  # the requester sees their own
    # one request per user and listing
    again = env.ask(lid, "citizen")
    assert again.status_code == 409 and again.json()["error"]["code"] == "request_exists"
    assert count(env.engine, "select count(*) from marketplace_requests") == 1
    # the owner sees it, with contact details, and the owner was notified
    mine = env.client.get(f"{LISTINGS}/{lid}/requests", headers=env.h["operator"]).json()
    assert [r["id"] for r in mine] == [req["id"]] and mine[0][
        "requester_email"
    ] == "citizen@example.org"
    assert (
        env.client.get(f"{LISTINGS}/{lid}", headers=env.h["operator"]).json()[
            "pending_request_count"
        ]
        == 1
    )
    assert [n["title"] for n in env.notes("operator")] == ["Someone asked for your listing"]
    # nobody else can list requests; the requester sees their own history
    assert env.client.get(f"{LISTINGS}/{lid}/requests", headers=env.h["other"]).status_code == 403
    page = env.client.get(f"{BASE}/requests/mine", headers=env.h["citizen"]).json()
    assert page["total"] == 1 and page["items"][0]["listing_title"] == "Office chairs"
    assert env.client.get(f"{BASE}/requests/mine", headers=env.h["other"]).json()["total"] == 0
    assert (
        env.client.get(f"{LISTINGS}/{lid}", headers=env.h["citizen"]).json()["my_request_status"]
        == "pending"
    )
    assert env.audits("marketplace_request.created") == 1


def test_accepting_reserves_the_listing_and_declines_the_others(env: Env) -> None:
    lid = env.listing()["id"]
    r1 = env.ask(lid, "citizen").json()
    r2 = env.ask(lid, "other").json()
    # strangers cannot decide (the request looks like it does not exist), neither can the requester
    for who in ("other", "operator2", "citizen"):
        assert env.decide(r1["id"], "accept", who).status_code == 404, who
    accepted = env.decide(r1["id"], "accept", "operator")
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
    assert env.listing_status(lid) == "reserved"
    states = {
        r["id"]: r["status"]
        for r in env.client.get(f"{LISTINGS}/{lid}/requests", headers=env.h["operator"]).json()
    }
    assert states == {r1["id"]: "accepted", r2["id"]: "declined"}
    # a reserved listing takes no new requests and accepts no second request
    assert env.ask(lid, "collector").status_code == 409
    assert env.decide(r2["id"], "accept", "operator").status_code == 409
    assert env.decide(r1["id"], "accept", "operator").status_code == 409
    assert [n["title"] for n in env.notes("citizen")] == ["Your request was accepted"]
    assert [n["title"] for n in env.notes("other")] == [
        "A listing you asked for was reserved for someone else"
    ]
    assert env.audits("marketplace_request.accepted") == 1
    # a declined user cannot ask again
    assert env.ask(lid, "other").status_code == 409


def test_releasing_a_reservation_offers_the_listing_again(env: Env) -> None:
    lid = env.listing()["id"]
    req = env.ask(lid, "citizen").json()
    env.decide(req["id"], "accept", "manager")  # a manager can act for the owner
    assert env.listing_status(lid) == "reserved"
    released = env.decide(req["id"], "decline", "operator")
    assert released.status_code == 200 and released.json()["status"] == "declined"
    assert env.listing_status(lid) == "published"
    assert env.ask(lid, "other").status_code == 201
    audit_count = env.audits("marketplace_request.declined")
    assert audit_count == 1
    # a decided request cannot be declined again
    assert env.decide(req["id"], "decline", "operator").status_code == 409


def test_withdrawing_and_asking_again(env: Env) -> None:
    lid = env.listing()["id"]
    req = env.ask(lid, "citizen").json()
    # only the requester withdraws
    assert env.decide(req["id"], "withdraw", "operator").status_code == 404
    assert env.decide(req["id"], "withdraw", "other").status_code == 404
    out = env.decide(req["id"], "withdraw", "citizen")
    assert (
        out.status_code == 200 and out.json()["status"] == "withdrawn" and out.json()["decided_at"]
    )
    assert env.decide(req["id"], "withdraw", "citizen").status_code == 409
    # withdrawn requests can be made again; it is the same row (unique per user and listing)
    again = env.ask(lid, "citizen", "Still interested")
    assert again.status_code == 201 and again.json()["id"] == req["id"]
    assert again.json()["status"] == "pending" and again.json()["decided_at"] is None
    assert count(env.engine, "select count(*) from marketplace_requests") == 1
    # withdrawing an accepted request releases the reservation
    env.decide(req["id"], "accept", "operator")
    assert env.listing_status(lid) == "reserved"
    env.decide(req["id"], "withdraw", "citizen")
    assert env.listing_status(lid) == "published"
    assert env.audits("marketplace_request.withdrawn") == 2


def test_closing_declines_pending_requests_and_tells_requesters(env: Env) -> None:
    lid = env.listing()["id"]
    pending = env.ask(lid, "citizen").json()
    env.act(lid, "close", reason="Sold elsewhere")
    mine = env.client.get(f"{BASE}/requests/mine", headers=env.h["citizen"]).json()["items"]
    assert [(r["id"], r["status"]) for r in mine] == [(pending["id"], "declined")]
    assert "A listing you asked for was closed" in [n["title"] for n in env.notes("citizen")]
    # closed listings leave the marketplace for everyone but the owner and managers
    assert env.client.get(f"{LISTINGS}/{lid}", headers=env.h["citizen"]).status_code == 404
    assert env.ask(lid, "other").status_code == 404
    assert (
        env.client.get(f"{LISTINGS}/{lid}", headers=env.h["manager"]).json()["status"] == "closed"
    )
    recorded = count(
        env.engine,
        "select count(*) from audit_logs where action='marketplace_listing.closed' "
        "and changes->>'reason' = 'Sold elsewhere'",
    )
    assert recorded == 1


def test_closing_a_reserved_listing_keeps_the_accepted_request_as_history(env: Env) -> None:
    lid = env.listing()["id"]
    accepted = env.ask(lid, "citizen").json()
    env.decide(accepted["id"], "accept", "operator")
    assert env.listing_status(lid) == "reserved"
    env.act(lid, "close")
    rows = env.client.get(f"{LISTINGS}/{lid}/requests", headers=env.h["operator"]).json()
    assert [(r["id"], r["status"]) for r in rows] == [(accepted["id"], "accepted")]
    # a closed listing can no longer be released back to the market
    assert env.decide(accepted["id"], "decline", "operator").status_code == 200
    assert env.listing_status(lid) == "closed"


def test_contact_details_are_private_to_owner_and_managers(env: Env) -> None:
    lid = env.listing()["id"]
    env.ask(lid, "citizen")
    as_manager = env.client.get(f"{LISTINGS}/{lid}/requests", headers=env.h["manager"]).json()
    assert as_manager[0]["requester_email"] == "citizen@example.org"
    assert env.client.get(f"{LISTINGS}/{lid}/requests", headers=env.h["citizen"]).status_code == 403
    # the public listing never carries an e-mail address
    assert "@" not in env.client.get(f"{LISTINGS}/{lid}", headers=env.h["other"]).text.replace(
        "example.org", ""
    )


def test_filters_search_sorting_and_pagination(env: Env) -> None:
    env.listing(
        title="Cardboard boxes", category="paper", quantity="200", unit="kg", pickup_city="Pune"
    )
    env.listing(title="Wooden pallets", category="wood", quantity="45", unit="units")
    env.listing(title="Aluminium offcuts", category="metals", quantity="80", unit="kg")
    env.listing(who="operator2", publish=False, title="Hidden draft", category="metals")
    h = env.h["citizen"]

    def titles(**params: Any) -> list[str]:
        response = env.client.get(LISTINGS, params=params, headers=h)
        assert response.status_code == 200, response.text
        return [i["title"] for i in response.json()["items"]]

    assert sorted(titles()) == ["Aluminium offcuts", "Cardboard boxes", "Wooden pallets"]
    assert titles(category="metals") == ["Aluminium offcuts"]
    assert titles(q="pallet") == ["Wooden pallets"]
    assert titles(q="pune") == ["Cardboard boxes"]
    assert titles(q="%") == []  # wildcard characters are literal
    assert titles(sort_by="quantity", order="desc") == [
        "Cardboard boxes",
        "Aluminium offcuts",
        "Wooden pallets",
    ]
    assert titles(sort_by="title", order="asc")[0] == "Aluminium offcuts"
    page = env.client.get(
        LISTINGS, params={"page_size": 2, "page": 2, "sort_by": "title", "order": "asc"}, headers=h
    ).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert env.client.get(LISTINGS, params={"category": "gold"}, headers=h).status_code == 422
    # `mine` is the caller's own, drafts included; a manager sees every listing
    assert (
        env.client.get(LISTINGS, params={"mine": True}, headers=env.h["operator2"]).json()["total"]
        == 1
    )
    assert env.client.get(LISTINGS, params={"mine": True}, headers=h).json()["total"] == 0
    assert env.client.get(LISTINGS, headers=env.h["manager"]).json()["total"] == 4
    assert titles(status="draft") == []


def test_check_constraints_back_the_rules(env: Env) -> None:
    lid = env.listing()["id"]
    with (
        env.engine.begin() as conn,
        pytest.raises(IntegrityError, match="closed_timestamp_consistent"),
    ):
        conn.execute(
            text("update marketplace_listings set status='closed' where id=:i"), {"i": lid}
        )
    with env.engine.begin() as conn, pytest.raises(IntegrityError, match="quantity_positive"):
        conn.execute(text("update marketplace_listings set quantity=0 where id=:i"), {"i": lid})
