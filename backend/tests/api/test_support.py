"""Help assistant, knowledge base and support tickets: permissions, answers, privacy, workflow."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.modules.support import assistant, knowledge, tickets
from tests.fixtures.api import bearer, create_user, login
from tests.fixtures.chain import Chain, chain  # noqa: F401 (fixture)

BASE = "/api/v1/support"
ROLES = ("citizen", "collector", "facility_operator", "manager", "administrator")


def seed(c: Chain) -> None:
    with sessionmaker(bind=c.engine, expire_on_commit=False)() as db:
        knowledge.seed_platform_help(db)


def ask(c: Chain, who: str, message: str, conversation_id: str | None = None) -> Any:
    body: dict[str, Any] = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return c.client.post(f"{BASE}/assistant/messages", json=body, headers=c.h[who])


def new_ticket(c: Chain, who: str = "citizen", **over: Any) -> dict[str, Any]:
    body = {
        "subject": "My reward is missing",
        "body": "I redeemed a bottle but nobody has it.",
    } | over
    response = c.client.post(f"{BASE}/tickets", json=body, headers=c.h[who])
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def audit_actions(c: Chain) -> list[str]:
    with c.engine.connect() as connection:
        rows = connection.execute(text("SELECT action FROM audit_logs ORDER BY occurred_at"))
        return [r[0] for r in rows]


# -- permissions -----------------------------------------------------------------------------------
def test_everything_needs_a_signed_in_user(chain: Chain) -> None:  # noqa: F811
    for method, path in (
        ("get", "/articles"),
        ("post", "/assistant/messages"),
        ("get", "/tickets/mine"),
        ("post", "/tickets"),
        ("get", "/tickets"),
        ("get", "/assistant/stats"),
    ):
        assert getattr(chain.client, method)(BASE + path).status_code == 401, path


def test_every_role_can_ask_but_only_staff_manage(chain: Chain) -> None:  # noqa: F811
    seed(chain)
    for who in ROLES:
        assert chain.client.get(f"{BASE}/articles", headers=chain.h[who]).status_code == 200
        assert ask(chain, who, "How do I report waste?").status_code == 200
    article = {
        "slug": "extra-help",
        "title": "Extra help article",
        "body": "A body that is long enough to be accepted.",
        "category": "Help",
        "source": "unit test",
    }
    for who in ("citizen", "collector", "facility_operator"):
        h = chain.h[who]
        assert chain.client.post(f"{BASE}/articles", json=article, headers=h).status_code == 403
        assert chain.client.get(f"{BASE}/tickets", headers=h).status_code == 403
        assert chain.client.get(f"{BASE}/assistant/stats", headers=h).status_code == 403
    for who in ("manager", "administrator"):
        h = chain.h[who]
        assert chain.client.get(f"{BASE}/tickets", headers=h).status_code == 200
        assert chain.client.get(f"{BASE}/assistant/stats", headers=h).status_code == 200


def test_a_user_without_the_permission_cannot_ask(chain: Chain, db_engine: Any) -> None:  # noqa: F811
    with db_engine.begin() as connection:  # a custom role that holds no support permission
        connection.execute(text("INSERT INTO roles (name, description) VALUES ('nobody', 'x')"))
    create_user(db_engine, email="nobody@example.org", roles=("nobody",))
    token = login(chain.client, "nobody@example.org")["access_token"]
    assert chain.client.get(f"{BASE}/articles", headers=bearer(token)).status_code == 403
    response = chain.client.post(
        f"{BASE}/assistant/messages", json={"message": "hi there"}, headers=bearer(token)
    )
    assert response.status_code == 403


# -- knowledge base --------------------------------------------------------------------------------
def test_seeding_is_idempotent_and_never_overwrites_a_staff_edit(chain: Chain) -> None:  # noqa: F811
    factory = sessionmaker(bind=chain.engine, expire_on_commit=False)
    with factory() as db:
        created, updated = knowledge.seed_platform_help(db)
    assert created >= 25 and updated == 0
    with factory() as db:
        assert knowledge.seed_platform_help(db) == (0, 0)
    articles = chain.client.get(
        f"{BASE}/articles", params={"page_size": 100}, headers=chain.h["manager"]
    ).json()["items"]
    mine = next(a for a in articles if a["slug"] == "forgot-password")
    assert mine["source"] == "platform-help"
    # A manager rewrites it: the source changes, so a later seed must not touch it.
    edited = chain.client.patch(
        f"{BASE}/articles/{mine['id']}",
        json={
            "body": "Local rule: ask the front desk to reset your password.",
            "source": "front desk",
        },
        headers=chain.h["manager"],
    )
    assert edited.status_code == 200
    with factory() as db:
        assert knowledge.seed_platform_help(db) == (0, 0)
    body = chain.client.get(f"{BASE}/articles/{mine['id']}", headers=chain.h["citizen"]).json()
    assert body["body"].startswith("Local rule")


def test_article_lifecycle_validation_and_visibility(chain: Chain) -> None:  # noqa: F811
    h = chain.h["manager"]
    payload = {
        "slug": "bulky-waste",
        "title": "How do I get rid of a sofa?",
        "body": "Book a bulky waste pickup with your municipality before putting it out.",
        "category": "Collections",
        "source": "City leaflet 2026",
        "keywords": "couch furniture mattress",
        "published": False,
    }
    for bad in ({"slug": "Bad Slug"}, {"slug": "bad--slug"}, {"body": "short"}, {"source": ""}):
        assert (
            chain.client.post(f"{BASE}/articles", json=payload | bad, headers=h).status_code == 422
        )
    created = chain.client.post(f"{BASE}/articles", json=payload, headers=h)
    assert created.status_code == 201, created.text
    article = created.json()
    assert (
        chain.client.post(f"{BASE}/articles", json=payload, headers=h).status_code == 409
    )  # slug is unique
    # Unpublished: invisible to a citizen (list, detail and the assistant), visible to staff.
    cit = chain.h["citizen"]
    listing = chain.client.get(
        f"{BASE}/articles", params={"include_unpublished": True}, headers=cit
    )
    assert article["id"] not in [a["id"] for a in listing.json()["items"]]
    assert chain.client.get(f"{BASE}/articles/{article['id']}", headers=cit).status_code == 404
    reply = ask(chain, "citizen", "How do I get rid of a sofa?").json()["reply"]
    assert reply["kind"] == "no_answer"
    staff_view = chain.client.get(
        f"{BASE}/articles", params={"include_unpublished": True}, headers=h
    )
    assert article["id"] in [a["id"] for a in staff_view.json()["items"]]
    # Publishing makes it answer, with its name as the source.
    chain.client.patch(f"{BASE}/articles/{article['id']}", json={"published": True}, headers=h)
    reply = ask(chain, "citizen", "How do I get rid of a sofa?").json()["reply"]
    assert reply["kind"] == "knowledge"
    assert reply["sources"][0]["title"] == "How do I get rid of a sofa?"
    assert "bulky waste pickup" in reply["content"]
    # Keywords are searched but never shown.
    assert "couch" not in reply["content"]
    found = ask(chain, "citizen", "what about a couch mattress").json()["reply"]
    assert found["kind"] == "knowledge"
    actions = audit_actions(chain)
    assert "knowledge_article.created" in actions and "knowledge_article.updated" in actions


# -- assistant -----------------------------------------------------------------------------------------
def test_answers_quote_a_source_and_unknown_questions_are_not_guessed(chain: Chain) -> None:  # noqa: F811
    seed(chain)
    ok = ask(chain, "citizen", "How do I redeem my points for a reward?")
    assert ok.status_code == 200
    body = ok.json()
    assert body["reply"]["kind"] == "knowledge" and body["suggest_ticket"] is False
    assert body["reply"]["sources"][0]["kind"] == "article"
    assert "claim code" in body["reply"]["content"]
    assert body["question"]["role"] == "user" and body["reply"]["role"] == "assistant"

    unknown = ask(chain, "citizen", "What is the capital of France?").json()
    assert unknown["reply"]["kind"] == "no_answer" and unknown["suggest_ticket"] is True
    assert unknown["reply"]["sources"] == []  # nothing is offered as if it were an answer
    assert "rather not guess" in unknown["reply"]["content"]


def test_near_misses_are_suggested_but_never_quoted(chain: Chain) -> None:  # noqa: F811
    seed(chain)
    reply = ask(chain, "citizen", "I need to speak to a human").json()["reply"]
    assert reply["kind"] == "no_answer"
    assert reply["sources"], "related articles should be offered"
    for source in reply["sources"]:
        assert source["title"] not in reply["content"]


def test_conversation_continues_and_belongs_to_its_owner(chain: Chain) -> None:  # noqa: F811
    seed(chain)
    first = ask(chain, "citizen", "How do I report waste?").json()
    second = ask(chain, "citizen", "What do the statuses mean?", first["conversation_id"]).json()
    assert second["conversation_id"] == first["conversation_id"]
    history = chain.client.get(
        f"{BASE}/assistant/conversations/{first['conversation_id']}", headers=chain.h["citizen"]
    ).json()
    assert [m["role"] for m in history["messages"]] == ["user", "assistant", "user", "assistant"]
    # Somebody else's conversation looks like a missing one, for reading and for asking.
    other = chain.h["collector"]
    url = f"{BASE}/assistant/conversations/{first['conversation_id']}"
    assert chain.client.get(url, headers=other).status_code == 404
    assert ask(chain, "collector", "hello there", first["conversation_id"]).status_code == 404
    assert chain.client.get(url, headers=chain.h["administrator"]).status_code == 404


@pytest.mark.parametrize("message", ["", "   ", "\x00\x01\x02", "x" * 1001])
def test_bad_messages_are_rejected(chain: Chain, message: str) -> None:  # noqa: F811
    assert ask(chain, "citizen", message).status_code == 422


def test_feedback_is_recorded_only_on_your_own_assistant_replies(chain: Chain) -> None:  # noqa: F811
    seed(chain)
    body = ask(chain, "citizen", "How do I report waste?").json()
    reply_id, question_id = body["reply"]["id"], body["question"]["id"]
    url = f"{BASE}/assistant/messages/{reply_id}/feedback"
    done = chain.client.post(url, json={"helpful": True}, headers=chain.h["citizen"])
    assert done.status_code == 200 and done.json()["helpful"] is True
    assert (
        chain.client.post(url, json={"helpful": True}, headers=chain.h["collector"]).status_code
        == 404
    )
    on_question = f"{BASE}/assistant/messages/{question_id}/feedback"
    assert (
        chain.client.post(
            on_question, json={"helpful": False}, headers=chain.h["citizen"]
        ).status_code
        == 404
    )
    stats = chain.client.get(f"{BASE}/assistant/stats", headers=chain.h["manager"]).json()
    assert (
        stats["answered_from_knowledge"] == 1
        and stats["rated"] == 1
        and stats["rated_helpful"] == 1
    )


def test_questions_about_your_own_records_use_your_records_only(chain: Chain) -> None:  # noqa: F811
    c = chain
    adjust = c.client.post(
        "/api/v1/rewards/adjustments",
        json={"user_id": str(c.ids["citizen"]), "points": 150, "description": "Test funding"},
        headers=c.h["manager"],
    )
    assert adjust.status_code == 201, adjust.text
    other = create_user(c.engine, email="other.citizen@example.org")
    assert other
    mine = ask(c, "citizen", "How many points do I have?").json()["reply"]
    assert mine["kind"] == "account_data" and "150 points" in mine["content"]
    assert mine["sources"][0]["kind"] == "account"
    # The same words from a person with no points say 0, never somebody else's figure.
    other_token = login(c.client, "other.citizen@example.org")["access_token"]
    zero = c.client.post(
        f"{BASE}/assistant/messages",
        json={"message": "How many points do I have?"},
        headers=bearer(other_token),
    ).json()["reply"]
    assert "0 points" in zero["content"] and "150" not in zero["content"]
    # A collector holds no rewards permission, so the data is refused, not guessed.
    refused = ask(c, "collector", "What is my points balance?").json()
    assert refused["reply"]["kind"] == "not_permitted" and refused["suggest_ticket"] is True
    assert "150" not in refused["reply"]["content"]
    assert "assistant.account_data_read" in audit_actions(c)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("How many points do I have?", "account_data"),
        ("what is my points balance", "account_data"),
        ("do I have enough points", "account_data"),
        ("what is the status of my reports", "account_data"),
        ("how do I redeem my points", "knowledge"),
        ("can I cancel my points redemption", "knowledge"),
        ("how can I earn more points", "knowledge"),
        ("how do I submit a report", "knowledge"),
        ("where do I use my reward points", "knowledge"),
    ],
)
def test_account_questions_are_told_apart_from_how_to_questions(
    chain: Chain,  # noqa: F811
    question: str,
    expected: str,
) -> None:
    seed(chain)
    assert ask(chain, "citizen", question).json()["reply"]["kind"] == expected


def test_report_and_ticket_counts_are_read_from_the_database(chain: Chain) -> None:  # noqa: F811
    c = chain
    none = ask(c, "citizen", "What is the status of my reports?").json()["reply"]
    assert "not submitted any waste reports" in none["content"]
    report = c.client.post(
        "/api/v1/waste-reports",
        json={"title": "Bags on the corner", "description": "Three bags"},
        headers=c.h["citizen"],
    )
    assert report.status_code == 201, report.text
    one = ask(c, "citizen", "What is the status of my reports?").json()["reply"]
    assert "1 report" in one["content"] and "1 submitted" in one["content"]
    new_ticket(c)
    tickets_reply = ask(c, "citizen", "What is the status of my support requests?").json()["reply"]
    assert "1 support request" in tickets_reply["content"] and "1 open" in tickets_reply["content"]


def test_guidance_entered_by_staff_answers_with_its_source(chain: Chain) -> None:  # noqa: F811
    c = chain
    plastic = c.category("plastic")
    created = c.client.post(
        "/api/v1/sorting-guide/guidance",
        json={
            "material_category_id": plastic,
            "disposal_method": "recycle",
            "title": "Plastic bottles",
            "instructions": "Rinse the bottle and place it in the blue recycling bin.",
            "preparation_notes": "Remove the cap and flatten the bottle.",
            "source_reference": "City recycling leaflet 2026",
        },
        headers=c.h["manager"],
    )
    assert created.status_code == 201, created.text
    reply = ask(c, "citizen", "Which bin does a plastic bottle go in?").json()["reply"]
    assert reply["kind"] == "knowledge"
    assert reply["sources"][0]["kind"] == "sorting_guidance"
    assert (
        "blue recycling bin" in reply["content"]
        and "City recycling leaflet 2026" in reply["content"]
    )
    # Switched off, it is no longer used.
    c.client.patch(
        f"/api/v1/sorting-guide/guidance/{created.json()['id']}",
        json={"is_active": False},
        headers=c.h["manager"],
    )
    again = ask(c, "citizen", "Which bin does a plastic bottle go in?").json()["reply"]
    assert again["kind"] == "no_answer"


def test_the_assistant_is_rate_limited_per_person(
    chain: Chain,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assistant, "MAX_ASSISTANT_MESSAGES_PER_WINDOW", 3)
    for _ in range(3):
        assert ask(chain, "citizen", "How do I report waste?").status_code == 200
    blocked = ask(chain, "citizen", "How do I report waste?")
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) >= 1
    assert ask(chain, "collector", "How do I report waste?").status_code == 200  # others unaffected


def test_old_conversations_are_purged_but_shared_ones_are_kept(chain: Chain) -> None:  # noqa: F811
    seed(chain)
    kept = ask(chain, "citizen", "How do I report waste?").json()["conversation_id"]
    gone = ask(chain, "citizen", "How do I redeem my points?").json()["conversation_id"]
    fresh = ask(chain, "citizen", "What do the statuses mean?").json()["conversation_id"]
    new_ticket(chain, conversation_id=kept, share_conversation=True)
    with chain.engine.begin() as connection:
        connection.execute(
            text("UPDATE assistant_conversations SET updated_at = :old WHERE id = ANY(:ids)"),
            {"old": dt.datetime.now(dt.UTC) - dt.timedelta(days=200), "ids": [kept, gone]},
        )
    with sessionmaker(bind=chain.engine)() as db:
        assert assistant.purge_old_conversations(db, older_than_days=90) == 1
    with chain.engine.connect() as connection:
        left = {
            str(r[0]) for r in connection.execute(text("SELECT id FROM assistant_conversations"))
        }
    assert left == {kept, fresh}


# -- tickets ------------------------------------------------------------------------------------------
def test_ticket_workflow_between_a_citizen_and_staff(chain: Chain) -> None:  # noqa: F811
    c = chain
    ticket = new_ticket(c)
    tid = ticket["id"]
    assert ticket["status"] == "open" and ticket["requester_name"] is None  # staff-only field
    assert c.client.get(f"{BASE}/tickets/mine", headers=c.h["citizen"]).json()["total"] == 1
    # Staff were told; another citizen and a collector cannot see it (it looks missing).
    staff_alerts = c.client.get("/api/v1/notifications", headers=c.h["manager"]).json()["items"]
    assert any("new support request" in n["title"] for n in staff_alerts)
    for who in ("collector", "facility_operator"):
        assert c.client.get(f"{BASE}/tickets/{tid}", headers=c.h[who]).status_code == 404
        assert (
            c.client.post(
                f"{BASE}/tickets/{tid}/replies", json={"body": "me too"}, headers=c.h[who]
            ).status_code
            == 404
        )
    seen = c.client.get(f"{BASE}/tickets/{tid}", headers=c.h["manager"]).json()
    assert seen["requester_name"] == "Test Person"

    # The first staff reply starts the work, assigns the replier and notifies the requester.
    replied = c.client.post(
        f"{BASE}/tickets/{tid}/replies",
        json={"body": "Please come to the counter."},
        headers=c.h["manager"],
    )
    assert replied.status_code == 200, replied.text
    detail = replied.json()
    assert detail["status"] == "in_progress" and detail["assignee_id"] == str(c.ids["manager"])
    assert detail["replies"][0]["is_staff"] is True and detail["reply_count"] == 1
    alerts = c.client.get("/api/v1/notifications", headers=c.h["citizen"]).json()["items"]
    assert any("Support replied" in n["title"] for n in alerts)

    resolved = c.client.patch(
        f"{BASE}/tickets/{tid}", json={"status": "resolved"}, headers=c.h["manager"]
    ).json()
    assert resolved["status"] == "resolved" and resolved["resolved_at"] is not None
    # The requester answers a resolved ticket: it reopens.
    again = c.client.post(
        f"{BASE}/tickets/{tid}/replies", json={"body": "Still not there."}, headers=c.h["citizen"]
    ).json()
    assert again["status"] == "open" and again["resolved_at"] is None
    assert [r["is_staff"] for r in again["replies"]] == [True, False]
    closed = c.client.post(f"{BASE}/tickets/{tid}/close", headers=c.h["citizen"]).json()
    assert closed["status"] == "closed"
    blocked = c.client.post(
        f"{BASE}/tickets/{tid}/replies", json={"body": "hello?"}, headers=c.h["citizen"]
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "ticket_closed"
    assert c.client.post(f"{BASE}/tickets/{tid}/close", headers=c.h["citizen"]).status_code == 200
    # Staff cannot close "as" the owner; the owner endpoint is the owner's.
    assert c.client.post(f"{BASE}/tickets/{tid}/close", headers=c.h["manager"]).status_code == 404
    actions = audit_actions(c)
    for expected in (
        "support_ticket.created",
        "support_ticket.replied",
        "support_ticket.updated",
        "support_ticket.closed_by_requester",
    ):
        assert expected in actions


def test_status_changes_follow_the_allowed_edges(chain: Chain) -> None:  # noqa: F811
    c = chain
    tid = new_ticket(c)["id"]

    def patch(status: str) -> Any:
        return c.client.patch(
            f"{BASE}/tickets/{tid}", json={"status": status}, headers=c.h["manager"]
        )

    assert patch("in_progress").status_code == 200
    assert patch("resolved").status_code == 200
    bad = patch("in_progress")  # resolved can only reopen or close
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "invalid_ticket_transition"
    assert patch("closed").status_code == 200
    reopen = patch("open")
    assert reopen.status_code == 409  # closed is terminal
    assert patch("not-a-status").status_code == 422


def test_assignment_rules(chain: Chain) -> None:  # noqa: F811
    c = chain
    tid = new_ticket(c)["id"]
    url = f"{BASE}/tickets/{tid}"
    mine = c.client.patch(url, json={"assign_to_me": True}, headers=c.h["manager"]).json()
    assert mine["assignee_id"] == str(c.ids["manager"])
    to_admin = c.client.patch(
        url, json={"assignee_id": str(c.ids["administrator"])}, headers=c.h["manager"]
    ).json()
    assert to_admin["assignee_id"] == str(c.ids["administrator"])
    notes = c.client.get("/api/v1/notifications", headers=c.h["administrator"]).json()["items"]
    assert any("assigned to you" in n["title"] for n in notes)
    # Only someone who can handle tickets may be given one.
    refused = c.client.patch(
        url, json={"assignee_id": str(c.ids["collector"])}, headers=c.h["manager"]
    )
    assert refused.status_code == 409
    gone = c.client.patch(
        url, json={"assignee_id": "00000000-0000-4000-8000-000000000000"}, headers=c.h["manager"]
    )
    assert gone.status_code == 404
    cleared = c.client.patch(url, json={"unassign": True}, headers=c.h["manager"]).json()
    assert cleared["assignee_id"] is None
    # A citizen cannot use the staff endpoint on their own ticket.
    assert c.client.patch(url, json={"status": "closed"}, headers=c.h["citizen"]).status_code == 403


def test_staff_list_filters(chain: Chain) -> None:  # noqa: F811
    c = chain
    first = new_ticket(c, subject="Reward missing")["id"]
    second = new_ticket(c, subject="Bin overflowing")["id"]
    c.client.patch(f"{BASE}/tickets/{first}", json={"assign_to_me": True}, headers=c.h["manager"])

    def ids(**params: Any) -> set[str]:
        page = c.client.get(f"{BASE}/tickets", params=params, headers=c.h["manager"]).json()
        return {t["id"] for t in page["items"]}

    assert ids() == {first, second}
    assert ids(assigned_to_me=True) == {first}
    assert ids(unassigned=True) == {second}
    assert ids(q="overflow") == {second}
    assert ids(status="open") == {first, second}
    assert ids(status="closed") == set()
    # Search text is data, not a pattern.
    assert ids(q="%") == set()


def test_the_conversation_is_shared_only_when_the_owner_says_so(chain: Chain) -> None:  # noqa: F811
    c = chain
    seed(c)
    conversation = ask(c, "citizen", "How do I report waste?").json()["conversation_id"]
    private = new_ticket(c, conversation_id=conversation, share_conversation=False)
    assert private["conversation_shared"] is False and private["conversation"] is None
    shared = new_ticket(c, conversation_id=conversation, share_conversation=True)
    assert shared["conversation_shared"] is True and len(shared["conversation"]) == 2
    staff = c.client.get(f"{BASE}/tickets/{private['id']}", headers=c.h["manager"]).json()
    assert staff["conversation"] is None
    before = audit_actions(c).count("support_ticket.transcript_viewed")
    viewed = c.client.get(f"{BASE}/tickets/{shared['id']}", headers=c.h["manager"]).json()
    assert len(viewed["conversation"]) == 2
    assert audit_actions(c).count("support_ticket.transcript_viewed") == before + 1
    # The owner reading their own ticket is not an access to be audited.
    c.client.get(f"{BASE}/tickets/{shared['id']}", headers=c.h["citizen"])
    assert audit_actions(c).count("support_ticket.transcript_viewed") == before + 1
    # You cannot attach somebody else's conversation, nor share nothing.
    foreign = c.client.post(
        f"{BASE}/tickets",
        json={
            "subject": "Hello there",
            "body": "Please look at this chat.",
            "conversation_id": conversation,
            "share_conversation": True,
        },
        headers=c.h["collector"],
    )
    assert foreign.status_code == 404
    nothing = c.client.post(
        f"{BASE}/tickets",
        json={"subject": "Hello there", "body": "Please look at this.", "share_conversation": True},
        headers=c.h["citizen"],
    )
    assert nothing.status_code == 400


def test_open_tickets_per_person_are_capped(
    chain: Chain,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tickets, "MAX_OPEN_TICKETS_PER_USER", 2)
    first = new_ticket(chain)["id"]
    new_ticket(chain)
    response = chain.client.post(
        f"{BASE}/tickets",
        json={"subject": "A third one", "body": "This should be refused."},
        headers=chain.h["citizen"],
    )
    assert (
        response.status_code == 409 and response.json()["error"]["code"] == "too_many_open_tickets"
    )
    chain.client.post(f"{BASE}/tickets/{first}/close", headers=chain.h["citizen"])
    assert new_ticket(chain)["status"] == "open"


@pytest.mark.parametrize(
    "payload",
    [
        {"subject": "ab", "body": "long enough body text"},
        {"subject": "Fine subject", "body": "short"},
        {"subject": "Fine subject", "body": "x" * 4001},
        {"subject": "\x00\x00\x00", "body": "long enough body text"},
    ],
)
def test_ticket_input_is_validated(chain: Chain, payload: dict[str, str]) -> None:  # noqa: F811
    response = chain.client.post(f"{BASE}/tickets", json=payload, headers=chain.h["citizen"])
    assert response.status_code == 422


def test_ticket_text_is_stored_as_plain_text(chain: Chain) -> None:  # noqa: F811
    script = "<script>alert(1)</script> please help me"
    ticket = new_ticket(chain, subject="Markup in subject", body=script)
    assert ticket["body"] == script  # never rewritten or executed server side; the UI renders text
    reply = chain.client.post(
        f"{BASE}/tickets/{ticket['id']}/replies",
        json={"body": "<img src=x onerror=alert(1)>"},
        headers=chain.h["manager"],
    ).json()
    assert reply["replies"][0]["body"] == "<img src=x onerror=alert(1)>"
