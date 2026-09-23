"""Media endpoints: upload (auth) and authorised fetch."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.auth.deps import AuthCtx, DbSession
from app.core.errors import NotFoundError
from app.core.rate_limit import rate_limit
from app.core.storage import get_storage
from app.media.service import load_media, store_upload

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit("upload"))])
async def upload_endpoint(
    ctx: AuthCtx, session: DbSession, file: UploadFile = File(...)
):
    if not ctx.has_perm("media:upload"):
        from app.core.errors import ForbiddenError

        raise ForbiddenError("Upload permission required.")
    org_id = ctx.org_id if ctx.org else None
    asset = await store_upload(session, org_id, uploader_user_id=ctx.user.id, upload=file)
    await session.commit()
    return {
        "id": asset.id,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "checksum_sha256": asset.checksum_sha256,
        "url": f"/api/v1/media/{asset.id}",
    }


@router.get("/{media_id}")
async def get_media_endpoint(media_id: uuid.UUID, ctx: AuthCtx, session: DbSession):
    asset = await load_media(session, media_id, ctx.org_id if ctx.org else None)
    if asset is None:
        raise NotFoundError("Media not found.")
    data = get_storage().open(asset.storage_key)
    return Response(
        content=data,
        media_type=asset.mime_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )
