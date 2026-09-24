"""Upload handling: validation, safe storage, DB record.

Uploads are untrusted: size-capped, MIME-allowlisted, extension checked
against the MIME, stored under organization-namespaced content keys, and
recorded with checksums. Filenames are never used for storage paths.
"""

from __future__ import annotations

import uuid

from fastapi import UploadFile

from app.core.config import settings
from app.core.db import AsyncSession, utcnow
from app.core.errors import ValidationApiError
from app.core.logging import get_logger
from app.core.storage import get_storage, media_key, new_media_id, sha256_hex
from app.media.models import MediaAsset, MediaKind, ScanStatus

log = get_logger("media")

_MIME_EXT = {
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/webp": {"webp"},
}

_MAGIC = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"RIFF", "image/webp"),
]


def _sniff_mime(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def store_upload(
    session: AsyncSession,
    organization_id: uuid.UUID | None,
    *,
    uploader_user_id: uuid.UUID | None,
    upload: UploadFile,
    kind: MediaKind = MediaKind.image,
) -> MediaAsset:
    if kind != MediaKind.image:
        raise ValidationApiError("Only image uploads are supported in V1.")
    data = await upload.read()
    if not data:
        raise ValidationApiError("Empty upload.")
    if len(data) > settings.max_upload_bytes:
        raise ValidationApiError(
            f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MiB limit."
        )
    sniffed = _sniff_mime(data)
    if sniffed is None or sniffed not in settings.allowed_upload_mimes:
        raise ValidationApiError("Unsupported or corrupted image file.")
    declared = (upload.content_type or "").split(";")[0].strip().lower()
    if declared and declared not in settings.allowed_upload_mimes:
        raise ValidationApiError("Unsupported file type.")
    original = upload.filename or "upload"
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext and ext not in _MIME_EXT[sniffed]:
        raise ValidationApiError("File extension does not match its content.")

    media_id = new_media_id()
    key = media_key(organization_id or "unscoped", media_id, sniffed.split("/")[1].replace("jpeg", "jpg"))
    get_storage().save(key, data)

    asset = MediaAsset(
        organization_id=organization_id,
        uploader_user_id=uploader_user_id,
        kind=kind,
        storage_key=key,
        original_filename=original[:255],
        mime_type=sniffed,
        size_bytes=len(data),
        checksum_sha256=sha256_hex(data),
        scan_status=ScanStatus.pending,
        uploaded_at=utcnow(),
    )
    session.add(asset)
    await session.flush()
    log.info(
        "media_stored",
        media_id=media_id,
        organization_id=str(organization_id),
        mime=sniffed,
        size=len(data),
    )
    return asset


async def load_media(session, media_id: uuid.UUID, organization_id: uuid.UUID | None):
    from sqlalchemy import select

    asset = (
        await session.execute(select(MediaAsset).where(MediaAsset.id == media_id))
    ).scalar_one_or_none()
    if asset is None:
        return None
    if organization_id is not None and asset.organization_id != organization_id:
        return None  # cross-tenant object access -> not found
    return asset
