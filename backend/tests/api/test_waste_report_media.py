"""Photo upload, retrieval and attachment: the whole path through HTTP, DB and storage."""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine, text

from app.integrations.file_storage import LocalFileStorage, StorageError
from app.modules.audit import service as audit_service
from app.modules.waste_reports.constants import MAX_UNATTACHED_UPLOADS_PER_USER
from tests.fixtures.api import ClientFactory, bearer, create_user, login

REPORTS = "/api/v1/waste-reports"
MEDIA = f"{REPORTS}/media"
MAX_BYTES = 200_000


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (64, 48), **kwargs: Any) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 120, 70)).save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


class Setup:
    def __init__(self, client: TestClient, engine: Engine, storage: Path) -> None:
        self.client, self.engine, self.storage = client, engine, storage
        self.owner = self._user("owner@example.org", ("citizen",))
        self.stranger = self._user("stranger@example.org", ("citizen",))
        self.manager = self._user("manager@example.org", ("manager",))

    def _user(self, email: str, roles: tuple[str, ...]) -> dict[str, str]:
        create_user(self.engine, email=email, roles=roles)
        return bearer(login(self.client, email)["access_token"])

    def upload(self, data: bytes, headers: dict[str, str] | None = None, **params: str) -> Any:
        return self.client.post(MEDIA, content=data, params=params, headers=headers or self.owner)

    def stored_files(self) -> list[Path]:
        return [p for p in self.storage.rglob("*") if p.is_file()]


@pytest.fixture
def s(make_client: ClientFactory, db_engine: Engine, tmp_path: Path) -> Setup:
    storage = tmp_path / "storage"
    client = make_client(file_storage_local_path=storage, max_upload_bytes=MAX_BYTES)
    return Setup(client, db_engine, storage)


def test_upload_stores_a_normalised_private_file_and_returns_metadata(s: Setup) -> None:
    response = s.upload(image_bytes("PNG", (64, 48)), filename="bin photo.png")
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["content_type"], body["width_px"], body["height_px"]) == ("image/png", 64, 48)
    assert body["content_path"] == f"{MEDIA}/{body['id']}/content"
    assert "storage_key" not in body and "sha256" not in body  # internals are not exposed

    [stored] = s.stored_files()
    assert stored.suffix == ".png" and stored.stat().st_size == body["size_bytes"]
    with s.engine.connect() as conn:
        row = conn.execute(
            text("SELECT original_filename, waste_report_id, sha256 FROM media_assets")
        ).one()
        assert (row.original_filename, row.waste_report_id) == ("bin photo.png", None)
        assert len(row.sha256) == 64
        audit = conn.execute(
            text("SELECT changes FROM audit_logs WHERE action='waste_report.media_uploaded'")
        ).scalar_one()
        assert audit["content_type"] == "image/png"


def test_the_clients_content_type_and_extension_are_not_trusted(s: Setup) -> None:
    response = s.client.post(
        MEDIA,
        content=image_bytes("JPEG"),
        params={"filename": "totally-a-pdf.pdf"},
        headers={**s.owner, "Content-Type": "application/pdf"},
    )
    assert response.status_code == 201
    assert response.json()["content_type"] == "image/jpeg"  # decided from the bytes
    assert s.stored_files()[0].suffix == ".jpg"


@pytest.mark.parametrize(
    ("data", "status", "code"),
    [
        (b"", 415, "unsupported_media_type"),
        (b"hello world", 415, "unsupported_media_type"),
        (
            b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
            415,
            "unsupported_media_type",
        ),
        (image_bytes("GIF"), 415, "unsupported_media_type"),
        (image_bytes("PNG")[:60], 415, "unsupported_media_type"),
        (image_bytes("PNG", (8, 8)), 422, "invalid_image"),
    ],
)
def test_unacceptable_files_are_rejected_and_nothing_is_stored(
    s: Setup, data: bytes, status: int, code: str
) -> None:
    response = s.upload(data)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert s.stored_files() == []
    with s.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM media_assets")).scalar_one() == 0


def test_a_decompression_bomb_is_rejected(s: Setup) -> None:
    buffer = io.BytesIO()
    Image.new("L", (8000, 8000)).save(buffer, format="PNG")
    assert len(buffer.getvalue()) < MAX_BYTES
    response = s.upload(buffer.getvalue())
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_image"


def test_oversized_upload_is_refused_by_declared_length(s: Setup) -> None:
    response = s.upload(b"\x89PNG" + b"0" * (MAX_BYTES + 1))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert s.stored_files() == []


def test_oversized_upload_without_content_length_is_stopped_while_streaming(s: Setup) -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(8):  # no Content-Length: sent chunked, 8 x 40 KB = 320 KB > limit
            yield b"0" * 40_000

    response = s.client.post(MEDIA, content=chunks(), headers=s.owner)
    assert response.status_code == 413
    assert s.stored_files() == []


def test_hostile_filenames_never_reach_the_filesystem_path(s: Setup) -> None:
    for name in ("../../etc/passwd", "..\\..\\windows\\system32\\x.png", "a/b/c.png", "x\x00y.png"):
        response = s.upload(image_bytes(), filename=name)
        assert response.status_code == 201, (name, response.text)
    files = s.stored_files()
    assert len(files) == 4
    for path in files:
        assert path.is_relative_to(s.storage.resolve())
        uuid.UUID(path.stem)  # the stored name is purely our generated UUID
    with s.engine.connect() as conn:
        names = {r[0] for r in conn.execute(text("SELECT original_filename FROM media_assets"))}
    assert "passwd" in names and not any("/" in n or "\\" in n or "\x00" in n for n in names)
    assert not (s.storage.parent / "etc").exists()


def test_gps_metadata_does_not_survive_upload_and_download(s: Setup) -> None:
    exif = Image.Exif()
    exif[0x010F] = "PhoneMakerXYZ"
    exif[0x8825] = {1: "N", 2: (17.0, 22.0, 30.0), 3: "E", 4: (78.0, 29.0, 0.0)}
    media = s.upload(image_bytes("JPEG", exif=exif.tobytes())).json()
    downloaded = s.client.get(media["content_path"], headers=s.owner)
    assert downloaded.status_code == 200
    assert b"PhoneMakerXYZ" not in downloaded.content
    with Image.open(io.BytesIO(downloaded.content)) as decoded:
        assert not decoded.getexif()
    assert b"PhoneMakerXYZ" not in s.stored_files()[0].read_bytes()


def test_content_is_served_with_defensive_headers(s: Setup) -> None:
    media = s.upload(image_bytes("WEBP")).json()
    response = s.client.get(media["content_path"], headers=s.owner)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "private, no-cache"
    disposition = response.headers["content-disposition"]
    assert disposition == f'inline; filename="media-{media["id"]}.webp"'  # never the client name


def test_only_the_uploader_and_staff_can_download(s: Setup) -> None:
    media = s.upload(image_bytes()).json()
    path = media["content_path"]
    assert s.client.get(path, headers=s.owner).status_code == 200
    assert s.client.get(path, headers=s.manager).status_code == 200  # read_all
    stranger = s.client.get(path, headers=s.stranger)
    unknown = s.client.get(f"{MEDIA}/{uuid.uuid4()}/content", headers=s.stranger)
    assert stranger.status_code == unknown.status_code == 404  # indistinguishable
    assert s.client.get(f"{MEDIA}/not-a-uuid/content", headers=s.owner).status_code == 422


def test_missing_bytes_for_an_existing_row_is_a_server_fault_not_a_404(s: Setup) -> None:
    media = s.upload(image_bytes()).json()
    s.stored_files()[0].unlink()
    response = s.client.get(media["content_path"], headers=s.owner)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"


# --------------------------------------------------------------------------- attachments


def _submit(s: Setup, media_ids: list[str], headers: dict[str, str] | None = None) -> Any:
    return s.client.post(
        REPORTS, json={"title": "Dumped sofa", "media_ids": media_ids}, headers=headers or s.owner
    )


def test_uploaded_photos_attach_to_a_report_and_appear_in_reads(s: Setup) -> None:
    first = s.upload(image_bytes()).json()
    second = s.upload(image_bytes("JPEG")).json()
    created = _submit(s, [first["id"], second["id"]])
    assert created.status_code == 201, created.text
    report = created.json()
    assert {m["id"] for m in report["media"]} == {first["id"], second["id"]}
    fetched = s.client.get(f"{REPORTS}/{report['id']}", headers=s.owner).json()
    assert {m["id"] for m in fetched["media"]} == {first["id"], second["id"]}
    listed = s.client.get(REPORTS, headers=s.owner).json()["items"][0]
    assert len(listed["media"]) == 2
    with s.engine.connect() as conn:
        rows = conn.execute(text("SELECT waste_report_id FROM media_assets")).all()
    assert {str(r[0]) for r in rows} == {report["id"]}


def test_a_photo_cannot_be_attached_twice(s: Setup) -> None:
    media = s.upload(image_bytes()).json()
    assert _submit(s, [media["id"]]).status_code == 201
    again = _submit(s, [media["id"]])
    assert again.status_code == 422 and again.json()["error"]["code"] == "invalid_media"


def test_someone_elses_or_unknown_photos_cannot_be_attached_and_look_identical(s: Setup) -> None:
    theirs = s.upload(image_bytes(), s.stranger).json()
    foreign = _submit(s, [theirs["id"]])
    unknown = _submit(s, [str(uuid.uuid4())])
    assert foreign.status_code == unknown.status_code == 422
    assert foreign.json()["error"]["message"] == unknown.json()["error"]["message"]
    with s.engine.connect() as conn:  # nothing was created or hijacked
        assert conn.execute(text("SELECT count(*) FROM waste_reports")).scalar_one() == 0
        assert conn.execute(text("SELECT waste_report_id FROM media_assets")).scalar_one() is None


def test_a_failed_submission_leaves_the_photos_attachable(s: Setup) -> None:
    media = s.upload(image_bytes()).json()
    bad = _submit(s, [media["id"], str(uuid.uuid4())])
    assert bad.status_code == 422
    assert _submit(s, [media["id"]]).status_code == 201


def test_concurrent_submissions_cannot_claim_the_same_photo(s: Setup) -> None:
    import threading

    media = s.upload(image_bytes()).json()
    results: list[Any] = []
    barrier = threading.Barrier(2)

    def go() -> None:
        barrier.wait()
        results.append(_submit(s, [media["id"]]))

    threads = [threading.Thread(target=go) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(r.status_code for r in results) == [201, 422]
    with s.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM waste_reports")).scalar_one() == 1


def test_idempotent_replay_does_not_reattach_or_fail_on_used_photos(s: Setup) -> None:
    media = s.upload(image_bytes()).json()
    body = {"title": "Dumped sofa", "media_ids": [media["id"]]}
    headers = {**s.owner, "Idempotency-Key": "media-key-00001"}
    first = s.client.post(REPORTS, json=body, headers=headers)
    again = s.client.post(REPORTS, json=body, headers=headers)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json() and len(again.json()["media"]) == 1


def test_unattached_upload_quota_is_enforced_per_user(s: Setup) -> None:
    tiny = image_bytes("PNG", (32, 32))
    for _ in range(MAX_UNATTACHED_UPLOADS_PER_USER):
        assert s.upload(tiny).status_code == 201
    over = s.upload(tiny)
    assert over.status_code == 409 and over.json()["error"]["code"] == "upload_quota_exceeded"
    assert s.upload(tiny, s.stranger).status_code == 201  # other users are unaffected
    assert (
        len(s.stored_files()) == MAX_UNATTACHED_UPLOADS_PER_USER + 1
    )  # the refusal stored nothing


def test_storage_failure_surfaces_as_a_server_error_without_a_database_row(
    s: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: object, key: str, content: bytes) -> None:
        raise StorageError("disk full")

    monkeypatch.setattr(LocalFileStorage, "save", broken)
    response = s.upload(image_bytes())
    assert response.status_code == 500
    with s.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM media_assets")).scalar_one() == 0


def test_a_database_failure_after_the_file_is_written_removes_the_file(
    s: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(audit_service, "record", explode)
    tolerant = TestClient(s.client.app, raise_server_exceptions=False)
    response = tolerant.post(MEDIA, content=image_bytes(), headers=s.owner)
    assert response.status_code == 500
    assert "db down" not in response.text  # internals are not leaked
    assert s.stored_files() == []  # the orphan file was cleaned up
    with s.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM media_assets")).scalar_one() == 0
