"""Waste-report use cases: submit, list, read, review and attach photos.

Every function takes the authenticated ``Principal`` and decides *what that caller may see or do*
here, on the server. Visibility rule: a caller with ``waste_reports:read_all`` sees every report;
otherwise only their own. A report the caller may not see is reported as 404, not 403, so report
ids cannot be probed.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.exceptions import (
    AppError,
    BadRequestError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.integrations.file_storage import FileStorage, StorageError
from app.integrations.file_storage.local import new_storage_key
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.waste_reports import repository
from app.modules.waste_reports.constants import (
    ALLOWED_TRANSITIONS,
    MAX_UNATTACHED_UPLOADS_PER_USER,
    WasteReportStatus,
)
from app.modules.waste_reports.errors import (
    IdempotencyKeyReusedError,
    InvalidMediaError,
    InvalidTransitionError,
    UploadQuotaExceededError,
)
from app.modules.waste_reports.images import normalize_image
from app.modules.waste_reports.models import MediaAsset, WasteReport
from app.modules.waste_reports.schemas import (
    MediaOut,
    ReviewRequest,
    WasteReportCreate,
    WasteReportOut,
    WasteReportQuery,
)

READ_ALL = "waste_reports:read_all"
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
MEDIA_PATH = "/api/v1/waste-reports/media/{id}/content"
_STORAGE_BACKEND = "local"


def media_out(media: MediaAsset) -> MediaOut:
    return MediaOut(
        id=media.id,
        content_type=media.content_type,
        size_bytes=media.size_bytes,
        width_px=media.width_px,
        height_px=media.height_px,
        created_at=media.created_at,
        content_path=MEDIA_PATH.format(id=media.id),
    )


def _out(report: WasteReport, media: list[MediaAsset]) -> WasteReportOut:
    return WasteReportOut(
        id=report.id,
        reporter_id=report.reporter_id,
        status=report.status,
        title=report.title,
        description=report.description,
        address_text=report.address_text,
        latitude=report.latitude,
        longitude=report.longitude,
        estimated_weight_kg=report.estimated_weight_kg,
        reported_at=report.reported_at,
        updated_at=report.updated_at,
        media=[media_out(m) for m in media],
    )


def _present(db: Session, report: WasteReport) -> WasteReportOut:
    return _out(report, repository.media_by_report(db, [report.id]).get(report.id, []))


def _fingerprint(payload: WasteReportCreate) -> str:
    body = payload.model_dump(mode="json")
    body["media_ids"] = sorted(body["media_ids"])
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def check_idempotency_key(key: str | None) -> str | None:
    if key is None:
        return None
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
        raise BadRequestError(
            "Idempotency-Key must be 8-64 characters: letters, digits, '-' or '_'"
        )
    return key


def _replay(existing: WasteReport, fingerprint: str) -> WasteReport:
    if existing.request_fingerprint != fingerprint:
        raise IdempotencyKeyReusedError(
            "This Idempotency-Key was already used with a different request body"
        )
    return existing


def create_report(
    db: Session,
    principal: Principal,
    payload: WasteReportCreate,
    *,
    idempotency_key: str | None,
    context: RequestContext,
) -> tuple[WasteReportOut, bool]:
    """Returns ``(report, created)``; ``created`` is False when an earlier identical request
    with the same idempotency key is being replayed."""
    fingerprint = _fingerprint(payload)
    if idempotency_key is not None:
        existing = repository.get_by_idempotency_key(db, principal.user_id, idempotency_key)
        if existing is not None:
            return _present(db, _replay(existing, fingerprint)), False

    attachments = _claimable_media(db, principal, payload.media_ids)
    try:
        report = repository.add(
            db,
            reporter_id=principal.user_id,
            title=payload.title,
            description=payload.description,
            address_text=payload.address_text,
            latitude=payload.latitude,
            longitude=payload.longitude,
            estimated_weight_kg=payload.estimated_weight_kg,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint if idempotency_key else None,
        )
    except IntegrityError:
        db.rollback()
        if idempotency_key is not None:
            # A concurrent request with the same key won the race: return its report.
            winner = repository.get_by_idempotency_key(db, principal.user_id, idempotency_key)
            if winner is not None:
                return _present(db, _replay(winner, fingerprint)), False
        raise
    for media in attachments:
        media.waste_report_id = report.id
    audit.record(
        db,
        action="waste_report.created",
        entity_type="waste_report",
        entity_id=report.id,
        actor_id=principal.user_id,
        context=context,
        changes={"attachments": len(attachments), "idempotent": idempotency_key is not None},
    )
    db.commit()
    db.refresh(report)
    return _out(report, attachments), True


def _claimable_media(
    db: Session, principal: Principal, media_ids: list[uuid.UUID]
) -> list[MediaAsset]:
    if not media_ids:
        return []
    found = repository.lock_media(db, media_ids)
    usable = [
        m for m in found if m.uploaded_by_id == principal.user_id and m.waste_report_id is None
    ]
    if len(usable) != len(media_ids):
        # One message for unknown / someone else's / already attached: no probing of upload ids.
        raise InvalidMediaError("One or more attachments are not available to attach")
    return usable


def list_reports(
    db: Session, principal: Principal, query: WasteReportQuery, params: PageParams
) -> Page[WasteReportOut]:
    own_only = query.mine or not principal.has(READ_ALL)
    reports, total = repository.list_page(
        db, query, params, reporter_id=principal.user_id if own_only else None
    )
    media = repository.media_by_report(db, [r.id for r in reports])
    return Page.build([_out(r, media.get(r.id, [])) for r in reports], total, params)


def _visible(report: WasteReport | None, principal: Principal) -> WasteReport:
    if report is None or (report.reporter_id != principal.user_id and not principal.has(READ_ALL)):
        raise NotFoundError("Waste report not found")
    return report


def get_report(db: Session, principal: Principal, report_id: uuid.UUID) -> WasteReportOut:
    return _present(db, _visible(repository.get(db, report_id), principal))


def review_report(
    db: Session,
    principal: Principal,
    report_id: uuid.UUID,
    payload: ReviewRequest,
    *,
    context: RequestContext,
) -> WasteReportOut:
    report = repository.get(db, report_id, for_update=True)
    if report is None:
        raise NotFoundError("Waste report not found")
    target = WasteReportStatus(payload.status)
    if target not in ALLOWED_TRANSITIONS[report.status]:
        raise InvalidTransitionError(
            f"A report that is '{report.status.value}' cannot move to '{target.value}'"
        )
    previous = report.status
    report.status = target
    audit.record(
        db,
        action="waste_report.status_changed",
        entity_type="waste_report",
        entity_id=report.id,
        actor_id=principal.user_id,
        context=context,
        changes={"from": previous.value, "to": target.value, "reason": payload.reason},
    )
    db.commit()
    db.refresh(report)
    return _present(db, report)


def _display_name(filename: str | None) -> str | None:
    """A safe, short label for the UI only; never used to build a path."""
    if not filename:
        return None
    name = unicodedata.normalize("NFKC", filename).replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:255] or None


def upload_media(
    db: Session,
    storage: FileStorage,
    principal: Principal,
    data: bytes,
    *,
    filename: str | None,
    max_bytes: int,
    context: RequestContext,
) -> MediaOut:
    if len(data) > max_bytes:
        raise PayloadTooLargeError(f"The file is larger than the {max_bytes}-byte limit")
    if repository.count_unattached(db, principal.user_id) >= MAX_UNATTACHED_UPLOADS_PER_USER:
        raise UploadQuotaExceededError(
            "Too many photos are waiting to be attached; submit a report or wait for cleanup"
        )
    image = normalize_image(data)
    key = new_storage_key(image.extension)
    try:
        storage.save(key, image.content)
    except StorageError as exc:
        raise AppError("The file could not be stored") from exc
    try:
        media = repository.add_media(
            db,
            uploaded_by_id=principal.user_id,
            storage_backend=_STORAGE_BACKEND,
            storage_key=key,
            original_filename=_display_name(filename),
            content_type=image.content_type,
            size_bytes=len(image.content),
            sha256=hashlib.sha256(image.content).hexdigest(),
            width_px=image.width,
            height_px=image.height,
        )
        audit.record(
            db,
            action="waste_report.media_uploaded",
            entity_type="media_asset",
            entity_id=media.id,
            actor_id=principal.user_id,
            context=context,
            changes={"content_type": image.content_type, "size_bytes": len(image.content)},
        )
        db.commit()
    except BaseException:
        db.rollback()
        storage.delete(key)  # do not leave a file that no row points to
        raise
    return media_out(media)


def read_media(
    db: Session, storage: FileStorage, principal: Principal, media_id: uuid.UUID
) -> tuple[bytes, MediaAsset]:
    media = repository.get_media(db, media_id)
    if media is None or (media.uploaded_by_id != principal.user_id and not principal.has(READ_ALL)):
        raise NotFoundError("File not found")
    try:
        return storage.read(media.storage_key), media
    except StorageError as exc:
        # The row exists but the bytes do not: an operational fault, not a client error.
        raise AppError("The file is currently unavailable") from exc
