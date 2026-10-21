"""Marketplace: listing expiry, close outcomes and photos."""

from __future__ import annotations

import datetime as dt
import io
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from app.modules.marketplace import expiry
from tests.fixtures.api import ClientFactory, bearer, create_user, login
from tests.fixtures.series import count

BASE = "/api/v1/marketplace"
LISTINGS = f"{BASE}/listings"


def picture(size: tuple[int, int] = (80, 60), fmt: str = "PNG", **save: Any) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (30, 130, 80)).save(buffer, format=fmt, **save)
    return buffer.getvalue()


class Env:
    def __init__(self, client: TestClient, engine: Engine, storage: Path) -> None:
        self.client, self.engine, self.storage = client, engine, storage
        self.h: dict[str, dict[str, str]] = {}
        self.ids: dict[str, uuid.UUID] = {}
        for who, role in (
            ("citizen", "citizen"),
            ("other", "citizen"),
            ("operator", "facility_operator"),
            ("operator2", "facility_operator"),
            ("manager", "manager"),
        ):
            email = f"{who}@example.org"
            self.ids[who] = create_user(engine, email=email, roles=(role,))
            self.h[who] = bearer(login(client, email)["access_token"])

    def listing(
        self, who: str = "operator", publish: bool = True, **publish_body: Any
    ) -> dict[str, Any]:
        created = self.client.post(
            LISTINGS,
            json={
                "title": "Office chairs",
                "category": "furniture",
                "quantity": "30",
                "unit": "units",
                "condition": "good",
            },
            headers=self.h[who],
        )
        assert created.status_code == 201, created.text
        body: dict[str, Any] = created.json()
        return self.act(body["id"], "publish", who, **publish_body) if publish else body

    def act(
        self, listing_id: str, action: str, who: str = "operator", **body: Any
    ) -> dict[str, Any]:
        response = self.client.post(
            f"{LISTINGS}/{listing_id}/{action}", json=body or None, headers=self.h[who]
        )
        assert response.status_code == 200, response.text
        out: dict[str, Any] = response.json()
        return out

    def photo(self, listing_id: str, data: bytes, who: str = "operator", **params: Any) -> Any:
        return self.client.post(
            f"{LISTINGS}/{listing_id}/photos", content=data, params=params, headers=self.h[who]
        )

    def sql(self, statement: str, **params: Any) -> None:
        with self.engine.begin() as connection:
            connection.execute(text(statement), params)

    def audits(self, action: str) -> int:
        return count(self.engine, "select count(*) from audit_logs where action=:a", a=action)

    def notes(self, who: str) -> list[str]:
        items = self.client.get("/api/v1/notifications", headers=self.h[who]).json()["items"]
        return [str(item["title"]) for item in items]


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine, tmp_path: Path) -> Env:
    return Env(make_client(file_storage_local_path=tmp_path), db_engine, tmp_path)


def _lapse(env: Env, listing_id: str, *, hours_from_now: float = -1) -> None:
    env.sql(
        "update marketplace_listings set expires_at = now() + make_interval(secs => :s) "
        "where id = :i",
        s=hours_from_now * 3600,
        i=listing_id,
    )


# -- expiry --------------------------------------------------------------------------------------
def test_publishing_sets_an_expiry_from_the_server_setting(env: Env) -> None:
    draft = env.listing(publish=False)
    assert draft["expires_at"] is None and draft["is_expired"] is False
    published = env.act(draft["id"], "publish")
    expires = dt.datetime.fromisoformat(published["expires_at"])
    lifetime = expires - dt.datetime.fromisoformat(published["published_at"])
    assert lifetime == dt.timedelta(days=30)
    assert published["is_expired"] is False and published["outcome"] is None


def test_the_owner_can_choose_the_duration_within_limits(env: Env) -> None:
    short = env.listing(duration_days=7)
    lifetime = dt.datetime.fromisoformat(short["expires_at"]) - dt.datetime.fromisoformat(
        short["published_at"]
    )
    assert lifetime == dt.timedelta(days=7)
    for bad in (0, 91, -3, "soon"):
        draft = env.listing(publish=False)
        response = env.client.post(
            f"{LISTINGS}/{draft['id']}/publish",
            json={"duration_days": bad},
            headers=env.h["operator"],
        )
        assert response.status_code == 422, bad
        unknown = env.client.post(
            f"{LISTINGS}/{draft['id']}/publish", json={"price": 5}, headers=env.h["operator"]
        )
        assert unknown.status_code == 422


def test_the_default_duration_is_configurable(
    make_client: ClientFactory, db_engine: Engine, tmp_path: Path
) -> None:
    env = Env(
        make_client(file_storage_local_path=tmp_path, marketplace_listing_days=5),
        db_engine,
        tmp_path,
    )
    published = env.listing()
    lifetime = dt.datetime.fromisoformat(published["expires_at"]) - dt.datetime.fromisoformat(
        published["published_at"]
    )
    assert lifetime == dt.timedelta(days=5)


def test_a_lapsed_listing_is_hidden_and_cannot_be_requested(env: Env) -> None:
    listing = env.listing()
    lid = listing["id"]
    _lapse(env, lid)
    # Other people no longer see it, in the list or by id.
    assert env.client.get(f"{LISTINGS}/{lid}", headers=env.h["citizen"]).status_code == 404
    assert env.client.get(LISTINGS, headers=env.h["citizen"]).json()["total"] == 0
    # The owner and managers still do, and it says so.
    for who in ("operator", "manager"):
        seen = env.client.get(f"{LISTINGS}/{lid}", headers=env.h[who]).json()
        assert seen["is_expired"] is True and seen["status"] == "published"
    assert env.client.get(LISTINGS, headers=env.h["operator"]).json()["total"] == 1
    # A manager can still try to request it, and is told why not.
    blocked = env.client.post(f"{LISTINGS}/{lid}/requests", json={}, headers=env.h["manager"])
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "listing_expired"


def test_a_reserved_listing_is_not_hidden_or_closed_when_its_expiry_passes(env: Env) -> None:
    reserved = env.listing()["id"]
    request = env.client.post(
        f"{LISTINGS}/{reserved}/requests", json={}, headers=env.h["citizen"]
    ).json()
    env.client.post(f"{BASE}/requests/{request['id']}/accept", headers=env.h["operator"])
    _lapse(env, reserved)
    # A reservation is being handed over: it is neither hidden nor closed by the job.
    assert env.client.get(f"{LISTINGS}/{reserved}", headers=env.h["other"]).status_code == 200
    assert _run_job(env).closed == 0
    assert (
        env.client.get(f"{LISTINGS}/{reserved}", headers=env.h["operator"]).json()["status"]
        == "reserved"
    )


def test_the_expiry_job_closes_lapsed_listings_and_tells_everyone(env: Env) -> None:
    lapsed = env.listing()["id"]
    fresh = env.listing()["id"]
    draft = env.listing(publish=False)["id"]
    ask = env.client.post(f"{LISTINGS}/{lapsed}/requests", json={}, headers=env.h["citizen"])
    assert ask.status_code == 201
    _lapse(env, lapsed)
    # A draft has no expiry, so the job cannot touch it even if a bad row appears.
    result = _run_job(env)
    assert (result.closed, result.announced) == (1, 0)

    closed = env.client.get(f"{LISTINGS}/{lapsed}", headers=env.h["operator"]).json()
    assert closed["status"] == "closed" and closed["outcome"] == "expired"
    assert closed["close_reason"] == expiry.EXPIRED_REASON and closed["closed_at"] is not None
    assert (
        env.client.get(f"{LISTINGS}/{fresh}", headers=env.h["citizen"]).json()["status"]
        == "published"
    )
    assert (
        env.client.get(f"{LISTINGS}/{draft}", headers=env.h["operator"]).json()["status"] == "draft"
    )
    mine = env.client.get(f"{BASE}/requests/mine", headers=env.h["citizen"]).json()["items"]
    assert mine[0]["status"] == "declined"
    assert "Your listing expired" in env.notes("operator")
    assert "A listing you asked for expired" in env.notes("citizen")
    assert env.audits("marketplace_listing.expired") == 1

    # Idempotent: a second run finds nothing to do.
    again = _run_job(env)
    assert (again.closed, again.announced) == (0, 0)
    assert env.audits("marketplace_listing.expired") == 1


def test_owners_are_warned_once_before_a_listing_lapses_and_renewing_resets_the_warning(
    env: Env,
) -> None:
    lid = env.listing()["id"]
    assert _run_job(env).announced == 0  # 30 days left
    _lapse(env, lid, hours_from_now=48)
    first = _run_job(env)
    assert (first.closed, first.announced) == (0, 1)
    assert env.notes("operator").count("Your listing expires soon") == 1
    assert _run_job(env).announced == 0  # once only

    renewed = env.act(lid, "renew", duration_days=10)
    lifetime = dt.datetime.fromisoformat(renewed["expires_at"]) - dt.datetime.now(dt.UTC)
    assert dt.timedelta(days=9, hours=23) < lifetime <= dt.timedelta(days=10)
    _lapse(env, lid, hours_from_now=24)
    assert _run_job(env).announced == 1  # warned again for the new period
    assert env.audits("marketplace_listing.renewed") == 1


def test_renewing_follows_the_rules(env: Env) -> None:
    lid = env.listing()["id"]
    url = f"{LISTINGS}/{lid}/renew"
    assert env.client.post(url, headers=env.h["citizen"]).status_code == 403
    assert env.client.post(url, headers=env.h["operator2"]).status_code == 403
    assert env.client.post(url).status_code == 401
    # An expired-but-not-yet-closed listing can still be renewed by its owner or a manager.
    _lapse(env, lid)
    assert env.client.post(url, headers=env.h["manager"]).status_code == 200
    assert env.client.get(f"{LISTINGS}/{lid}", headers=env.h["citizen"]).status_code == 200
    # Drafts and closed listings cannot be renewed.
    draft = env.listing(publish=False)["id"]
    assert (
        env.client.post(f"{LISTINGS}/{draft}/renew", headers=env.h["operator"]).status_code == 409
    )
    env.act(lid, "close")
    assert env.client.post(url, headers=env.h["operator"]).status_code == 409
    # Once the job has closed it, it stays closed.
    other = env.listing()["id"]
    _lapse(env, other)
    _run_job(env)
    response = env.client.post(f"{LISTINGS}/{other}/renew", headers=env.h["operator"])
    assert (
        response.status_code == 409 and response.json()["error"]["code"] == "invalid_listing_state"
    )


# -- outcomes ------------------------------------------------------------------------------------
def test_closing_records_how_the_listing_ended(env: Env) -> None:
    withdrawn = env.listing()["id"]
    assert env.act(withdrawn, "close")["outcome"] == "withdrawn"

    reserved = env.listing()["id"]
    request = env.client.post(
        f"{LISTINGS}/{reserved}/requests", json={}, headers=env.h["citizen"]
    ).json()
    env.client.post(f"{BASE}/requests/{request['id']}/accept", headers=env.h["operator"])
    done = env.act(reserved, "close", outcome="handed_over", reason="Collected on Friday")
    assert done["outcome"] == "handed_over" and done["close_reason"] == "Collected on Friday"
    assert "The hand-over was recorded as complete" in env.notes("citizen")
    assert env.audits("marketplace_listing.closed") == 2


def test_handed_over_needs_a_reservation_and_expired_cannot_be_chosen(env: Env) -> None:
    lid = env.listing()["id"]
    for outcome, code in (("handed_over", 409), ("expired", 422), ("bogus", 422)):
        response = env.client.post(
            f"{LISTINGS}/{lid}/close", json={"outcome": outcome}, headers=env.h["operator"]
        )
        assert response.status_code == code, outcome
    assert (
        env.client.get(f"{LISTINGS}/{lid}", headers=env.h["operator"]).json()["status"]
        == "published"
    )


def test_withdrawing_a_reserved_listing_tells_the_person_it_was_reserved_for(env: Env) -> None:
    lid = env.listing()["id"]
    request = env.client.post(
        f"{LISTINGS}/{lid}/requests", json={}, headers=env.h["citizen"]
    ).json()
    env.client.post(f"{BASE}/requests/{request['id']}/accept", headers=env.h["operator"])
    env.act(lid, "close")
    assert "A listing reserved for you was withdrawn" in env.notes("citizen")


def test_the_database_refuses_inconsistent_expiry_and_outcome(env: Env) -> None:
    draft = env.listing(publish=False)["id"]
    published = env.listing()["id"]
    with pytest.raises(IntegrityError, match="expiry_needs_publication"):
        env.sql("update marketplace_listings set expires_at = now() where id = :i", i=draft)
    with pytest.raises(IntegrityError, match="outcome_only_when_closed"):
        env.sql("update marketplace_listings set outcome = 'expired' where id = :i", i=published)
    with pytest.raises(IntegrityError, match="outcome_valid"):
        env.sql(
            "update marketplace_listings set outcome = 'sold', status = 'closed', "
            "closed_at = now() where id = :i",
            i=published,
        )


# -- photos --------------------------------------------------------------------------------------
def test_a_photo_is_stored_re_encoded_and_served_with_safe_headers(env: Env) -> None:
    lid = env.listing()["id"]
    # An image that carries GPS metadata: it must not survive.
    source = Image.new("RGB", (120, 90), (200, 40, 40))
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (17.0, 22.0, 0.0), 3: "E", 4: (78.0, 29.0, 0.0)}
    buffer = io.BytesIO()
    source.save(buffer, format="JPEG", exif=exif)
    assert b"Exif" in buffer.getvalue()

    response = env.photo(lid, buffer.getvalue(), caption="  Front view  ")
    assert response.status_code == 201, response.text
    photo = response.json()
    assert (photo["position"], photo["caption"], photo["width_px"], photo["height_px"]) == (
        0,
        "Front view",
        120,
        90,
    )
    listing = env.client.get(f"{LISTINGS}/{lid}", headers=env.h["citizen"]).json()
    assert [p["id"] for p in listing["photos"]] == [photo["id"]]

    content = env.client.get(f"{BASE}/photos/{photo['id']}/content", headers=env.h["citizen"])
    assert content.status_code == 200 and content.headers["content-type"] == "image/jpeg"
    assert content.headers["x-content-type-options"] == "nosniff"
    assert content.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert b"Exif" not in content.content and b"GPS" not in content.content
    assert Image.open(io.BytesIO(content.content)).size == (120, 90)
    assert env.audits("marketplace_listing.photo_added") == 1
    assert len(list(env.storage.rglob("*.jpg"))) == 1


def test_photo_access_and_ownership_rules(env: Env) -> None:
    lid = env.listing(publish=False)["id"]
    assert env.client.post(f"{LISTINGS}/{lid}/photos", content=picture()).status_code == 401
    # Someone else's draft does not exist as far as they can tell.
    assert env.photo(lid, picture(), who="citizen").status_code == 404
    assert env.photo(lid, picture(), who="operator2").status_code == 404
    uploaded = env.photo(lid, picture(), who="operator").json()
    # A manager may add and remove photos on someone else's listing.
    assert env.photo(lid, picture(), who="manager").status_code == 201
    # Drafts are private, and so are their photos (404, the same as an unknown id).
    for who in ("citizen", "operator2"):
        got = env.client.get(f"{BASE}/photos/{uploaded['id']}/content", headers=env.h[who])
        assert got.status_code == 404
    assert (
        env.client.get(
            f"{BASE}/photos/{uploaded['id']}/content", headers=env.h["operator"]
        ).status_code
        == 200
    )
    env.act(lid, "publish")
    assert (
        env.client.get(
            f"{BASE}/photos/{uploaded['id']}/content", headers=env.h["citizen"]
        ).status_code
        == 200
    )
    # Another person cannot delete it; it is not found when the listing id does not match.
    url = f"{LISTINGS}/{lid}/photos/{uploaded['id']}"
    assert env.client.delete(url, headers=env.h["citizen"]).status_code == 403
    other_listing = env.listing()["id"]
    wrong = env.client.delete(
        f"{LISTINGS}/{other_listing}/photos/{uploaded['id']}", headers=env.h["operator"]
    )
    assert wrong.status_code == 404
    assert (
        env.client.get(
            f"{BASE}/photos/{uploaded['id']}/content", headers=env.h["citizen"]
        ).status_code
        == 200
    )


def test_photos_of_a_lapsed_listing_are_hidden_like_the_listing(env: Env) -> None:
    lid = env.listing()["id"]
    photo = env.photo(lid, picture()).json()
    _lapse(env, lid)
    url = f"{BASE}/photos/{photo['id']}/content"
    assert env.client.get(url, headers=env.h["citizen"]).status_code == 404
    assert env.client.get(url, headers=env.h["operator"]).status_code == 200


def test_at_most_four_photos_and_positions_never_repeat(env: Env) -> None:
    lid = env.listing()["id"]
    ids = [env.photo(lid, picture((60 + i, 60))).json()["id"] for i in range(4)]
    full = env.photo(lid, picture())
    assert full.status_code == 409 and full.json()["error"]["code"] == "photo_limit_reached"
    assert (
        env.client.delete(
            f"{LISTINGS}/{lid}/photos/{ids[1]}", headers=env.h["operator"]
        ).status_code
        == 204
    )
    again = env.photo(lid, picture())
    assert again.status_code == 201 and again.json()["position"] == 4
    listing = env.client.get(f"{LISTINGS}/{lid}", headers=env.h["citizen"]).json()
    assert [p["position"] for p in listing["photos"]] == [0, 2, 3, 4]
    assert env.audits("marketplace_listing.photo_removed") == 1


def test_deleting_a_photo_removes_the_row_and_the_file(env: Env) -> None:
    lid = env.listing()["id"]
    photo = env.photo(lid, picture()).json()
    assert len(list(env.storage.rglob("*.png"))) == 1
    assert (
        env.client.delete(
            f"{LISTINGS}/{lid}/photos/{photo['id']}", headers=env.h["operator"]
        ).status_code
        == 204
    )
    assert list(env.storage.rglob("*.png")) == []
    assert (
        env.client.get(
            f"{BASE}/photos/{photo['id']}/content", headers=env.h["operator"]
        ).status_code
        == 404
    )
    assert (
        env.client.delete(
            f"{LISTINGS}/{lid}/photos/{photo['id']}", headers=env.h["operator"]
        ).status_code
        == 404
    )


def test_photos_cannot_change_on_reserved_or_closed_listings(env: Env) -> None:
    lid = env.listing()["id"]
    photo = env.photo(lid, picture()).json()
    request = env.client.post(
        f"{LISTINGS}/{lid}/requests", json={}, headers=env.h["citizen"]
    ).json()
    env.client.post(f"{BASE}/requests/{request['id']}/accept", headers=env.h["operator"])
    assert env.photo(lid, picture()).status_code == 409
    assert (
        env.client.delete(
            f"{LISTINGS}/{lid}/photos/{photo['id']}", headers=env.h["operator"]
        ).status_code
        == 409
    )
    env.act(lid, "close")
    assert env.photo(lid, picture()).status_code == 409


@pytest.mark.parametrize(
    ("data", "status", "code"),
    [
        (b"not an image at all", 415, None),
        (b"", 415, None),
        (b"GIF89a" + b"\x00" * 40, 415, None),
        (picture((8, 8)), 422, "invalid_image"),  # smaller than the minimum side
    ],
)
def test_bad_uploads_are_rejected_and_leave_nothing_behind(
    env: Env, data: bytes, status: int, code: str | None
) -> None:
    lid = env.listing()["id"]
    response = env.photo(lid, data)
    assert response.status_code == status, response.text
    if code:
        assert response.json()["error"]["code"] == code
    assert list(env.storage.rglob("*.*")) == []
    assert env.client.get(f"{LISTINGS}/{lid}", headers=env.h["citizen"]).json()["photos"] == []


def test_oversized_uploads_are_refused_before_decoding(
    make_client: ClientFactory, db_engine: Engine, tmp_path: Path
) -> None:
    env = Env(
        make_client(file_storage_local_path=tmp_path, max_upload_bytes=2000), db_engine, tmp_path
    )
    lid = env.listing()["id"]
    noisy = Image.effect_noise((200, 200), 80).convert("RGB")
    buffer = io.BytesIO()
    noisy.save(buffer, format="PNG")
    assert len(buffer.getvalue()) > 2000
    response = env.photo(lid, buffer.getvalue())
    assert response.status_code == 413
    assert list(tmp_path.rglob("*.*")) == []


def test_the_caption_is_validated(env: Env) -> None:
    lid = env.listing()["id"]
    assert env.photo(lid, picture(), caption="x" * 201).status_code == 422
    assert env.photo(lid, picture(), caption="").status_code == 422
    assert env.photo(lid, picture()).json()["caption"] is None


def test_a_storage_failure_leaves_no_row(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.integrations.file_storage import StorageError
    from app.integrations.file_storage.local import LocalFileStorage

    def broken(self: LocalFileStorage, key: str, content: bytes) -> None:
        raise StorageError("disk full")

    monkeypatch.setattr(LocalFileStorage, "save", broken)
    lid = env.listing()["id"]
    response = env.photo(lid, picture())
    assert response.status_code >= 500
    assert env.client.get(f"{LISTINGS}/{lid}", headers=env.h["operator"]).json()["photos"] == []


def test_photo_check_constraints(env: Env) -> None:
    lid = env.listing()["id"]
    env.photo(lid, picture())
    with pytest.raises(IntegrityError, match="uq_marketplace_photos_listing_position"):
        env.sql(
            "insert into marketplace_listing_photos (listing_id, uploaded_by_id, position, "
            "storage_backend, storage_key, content_type, size_bytes, sha256, width_px, height_px) "
            "select listing_id, uploaded_by_id, position, 'local', 'dup-key', 'image/png', 1, "
            "repeat('a', 64), 1, 1 from marketplace_listing_photos"
        )


def _run_job(env: Env) -> expiry.ExpiryResult:
    from sqlalchemy.orm import Session

    with Session(env.engine) as db:
        return expiry.run(db)
