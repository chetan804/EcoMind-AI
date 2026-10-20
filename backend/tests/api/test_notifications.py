"""Notifications: strictly per-user listing, read state and counters."""

from __future__ import annotations

import uuid

from tests.fixtures.chain import Chain, chain  # noqa: F401 (fixture)

BASE = "/api/v1/notifications"


def assign_task(c: Chain) -> str:
    task = c.client.post(
        "/api/v1/collection/tasks",
        json={"title": "Pickup", "address_text": "1 Road"},
        headers=c.h["manager"],
    ).json()["id"]
    r = c.client.post(
        f"/api/v1/collection/tasks/{task}/assign",
        json={"assignee_id": str(c.ids["collector"])},
        headers=c.h["manager"],
    )
    assert r.status_code == 200, r.text
    return str(task)


def test_requires_authentication(chain: Chain) -> None:  # noqa: F811
    for method, path in (("get", ""), ("get", "/unread-count"), ("post", "/read-all")):
        assert getattr(chain.client, method)(BASE + path).status_code == 401


def test_assignment_notifies_only_the_assignee(chain: Chain) -> None:  # noqa: F811
    task = assign_task(chain)
    mine = chain.client.get(BASE, headers=chain.h["collector"]).json()
    assert mine["total"] == 1
    n = mine["items"][0]
    assert n["category"] == "collection" and n["read_at"] is None
    assert n["entity_type"] == "collection_task" and n["entity_id"] == task
    assert chain.client.get(BASE, headers=chain.h["citizen"]).json()["total"] == 0
    assert chain.client.get(BASE, headers=chain.h["facility_operator"]).json()["total"] == 0
    count = chain.client.get(f"{BASE}/unread-count", headers=chain.h["collector"]).json()
    assert count == {"unread": 1}
    assert chain.client.get(f"{BASE}/unread-count", headers=chain.h["citizen"]).json() == {
        "unread": 0
    }


def test_mark_read_is_idempotent_and_private(chain: Chain) -> None:  # noqa: F811
    assign_task(chain)
    nid = chain.client.get(BASE, headers=chain.h["collector"]).json()["items"][0]["id"]
    # someone else cannot read it or learn that it exists
    for who in ("citizen", "facility_operator"):
        r = chain.client.post(f"{BASE}/{nid}/read", headers=chain.h[who])
        assert r.status_code == 404, who
    assert (
        chain.client.get(f"{BASE}/unread-count", headers=chain.h["collector"]).json()["unread"] == 1
    )
    first = chain.client.post(f"{BASE}/{nid}/read", headers=chain.h["collector"])
    assert first.status_code == 200 and first.json()["read_at"] is not None
    second = chain.client.post(f"{BASE}/{nid}/read", headers=chain.h["collector"])
    assert second.json()["read_at"] == first.json()["read_at"]  # not re-stamped
    assert (
        chain.client.get(f"{BASE}/unread-count", headers=chain.h["collector"]).json()["unread"] == 0
    )
    assert (
        chain.client.post(f"{BASE}/{uuid.uuid4()}/read", headers=chain.h["collector"]).status_code
        == 404
    )


def test_read_all_and_filters(chain: Chain) -> None:  # noqa: F811
    assign_task(chain)
    assign_task(chain)
    h = chain.h["collector"]
    assert chain.client.get(BASE, params={"unread_only": "true"}, headers=h).json()["total"] == 2
    assert chain.client.get(BASE, params={"category": "reward"}, headers=h).json()["total"] == 0
    assert chain.client.get(BASE, params={"category": "bogus"}, headers=h).status_code == 422
    done = chain.client.post(f"{BASE}/read-all", headers=h)
    assert done.json() == {"marked": 2}
    assert chain.client.post(f"{BASE}/read-all", headers=h).json() == {"marked": 0}
    assert chain.client.get(BASE, params={"unread_only": "true"}, headers=h).json()["total"] == 0
    assert chain.client.get(BASE, headers=h).json()["total"] == 2
    # read-all never touches other users
    assign_task(chain)
    other = chain.client.post(f"{BASE}/read-all", headers=chain.h["citizen"])
    assert other.json() == {"marked": 0}
    assert chain.client.get(f"{BASE}/unread-count", headers=h).json()["unread"] == 1
    page = chain.client.get(BASE, params={"page_size": 2, "page": 2}, headers=h).json()
    assert page["total"] == 3 and len(page["items"]) == 1
