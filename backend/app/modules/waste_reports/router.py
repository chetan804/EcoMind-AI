"""Waste-report endpoints, mounted at ``/api/v1/waste-reports``."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import AppSettings, DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.core.exceptions import BadRequestError, PayloadTooLargeError
from app.integrations.file_storage import FileStorage, LocalFileStorage
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_any_permission, require_permissions
from app.modules.waste_reports import service
from app.modules.waste_reports.constants import WasteReportStatus
from app.modules.waste_reports.schemas import (
    MediaOut,
    ReviewRequest,
    SortField,
    WasteReportCreate,
    WasteReportOut,
    WasteReportQuery,
)

router = APIRouter()

CanCreate = Annotated[Principal, Depends(require_permissions("waste_reports:create"))]
CanRead = Annotated[
    Principal,
    Depends(require_any_permission("waste_reports:read_own", "waste_reports:read_all")),
]
CanReview = Annotated[Principal, Depends(require_permissions("waste_reports:review"))]
Pagination = Annotated[PageParams, Depends(page_params)]


def get_storage(settings: AppSettings) -> FileStorage:
    return LocalFileStorage(settings.file_storage_local_path)


Storage = Annotated[FileStorage, Depends(get_storage)]


@router.post("", response_model=WasteReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: WasteReportCreate,
    request: Request,
    response: Response,
    db: DbSession,
    principal: CanCreate,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WasteReportOut:
    """Submit a report. Send an ``Idempotency-Key`` header to make retries safe: a repeat of the
    same request returns the original report (200, ``Idempotent-Replayed: true``)."""
    key = service.check_idempotency_key(idempotency_key)
    report, created = service.create_report(
        db,
        principal,
        payload,
        idempotency_key=key,
        context=RequestContext.from_request(request),
    )
    if not created:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return report


@router.get("", response_model=Page[WasteReportOut])
def list_reports(
    db: DbSession,
    principal: CanRead,
    params: Pagination,
    status_filter: Annotated[WasteReportStatus | None, Query(alias="status")] = None,
    q: Annotated[
        str | None, Query(max_length=100, description="Search title, text, address")
    ] = None,
    mine: Annotated[bool, Query(description="Only my own reports")] = False,
    reported_from: dt.datetime | None = None,
    reported_to: dt.datetime | None = None,
    min_latitude: Annotated[decimal.Decimal | None, Query(ge=-90, le=90)] = None,
    max_latitude: Annotated[decimal.Decimal | None, Query(ge=-90, le=90)] = None,
    min_longitude: Annotated[decimal.Decimal | None, Query(ge=-180, le=180)] = None,
    max_longitude: Annotated[decimal.Decimal | None, Query(ge=-180, le=180)] = None,
    sort_by: SortField = "reported_at",
    order: SortOrder = SortOrder.DESC,
) -> Page[WasteReportOut]:
    if reported_from and reported_to and reported_from > reported_to:
        raise BadRequestError("reported_from must not be after reported_to")
    if any(v is not None for v in (min_latitude, max_latitude, min_longitude, max_longitude)):
        if (
            min_latitude is None
            or max_latitude is None
            or min_longitude is None
            or max_longitude is None
        ):
            raise BadRequestError(
                "an area filter needs min_latitude, max_latitude, min_longitude and "
                "max_longitude together"
            )
        if min_latitude > max_latitude or min_longitude > max_longitude:
            raise BadRequestError("an area filter's minimum must not exceed its maximum")
    query = WasteReportQuery(
        status=status_filter,
        q=q,
        mine=mine,
        reported_from=reported_from,
        reported_to=reported_to,
        min_latitude=min_latitude,
        max_latitude=max_latitude,
        min_longitude=min_longitude,
        max_longitude=max_longitude,
        sort_by=sort_by,
        order=order,
    )
    return service.list_reports(db, principal, query, params)


# Media routes are declared before ``/{report_id}`` so "media" is never read as an id.
@router.post("/media", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_media(
    request: Request,
    db: DbSession,
    storage: Storage,
    settings: AppSettings,
    principal: CanCreate,
    filename: Annotated[str | None, Query(max_length=255)] = None,
) -> MediaOut:
    """Upload one photo as the raw request body (JPEG, PNG or WebP).

    The size limit is enforced while streaming, before the body is buffered in full. The image is
    validated and re-encoded; EXIF/GPS metadata is stripped. Attach it by sending its ``id`` in
    ``media_ids`` when creating a report.
    """
    limit = settings.max_upload_bytes
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise PayloadTooLargeError(f"The file is larger than the {limit}-byte limit")
    chunks: list[bytes] = []
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > limit:
            raise PayloadTooLargeError(f"The file is larger than the {limit}-byte limit")
        chunks.append(chunk)
    return await run_in_threadpool(
        service.upload_media,
        db,
        storage,
        principal,
        b"".join(chunks),
        filename=filename,
        max_bytes=limit,
        context=RequestContext.from_request(request),
    )


@router.get("/media/{media_id}/content")
def media_content(
    media_id: uuid.UUID, db: DbSession, storage: Storage, principal: CanRead
) -> Response:
    data, media = service.read_media(db, storage, principal, media_id)
    extension = media.storage_key.rsplit(".", 1)[-1]
    return Response(
        content=data,
        media_type=media.content_type,
        headers={
            "Content-Disposition": f'inline; filename="media-{media.id}.{extension}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-cache",
        },
    )


@router.get("/{report_id}", response_model=WasteReportOut)
def get_report(report_id: uuid.UUID, db: DbSession, principal: CanRead) -> WasteReportOut:
    return service.get_report(db, principal, report_id)


@router.post("/{report_id}/review", response_model=WasteReportOut)
def review_report(
    report_id: uuid.UUID,
    payload: ReviewRequest,
    request: Request,
    db: DbSession,
    principal: CanReview,
) -> WasteReportOut:
    """Move a report through the review workflow; only the transitions in the docs are allowed."""
    return service.review_report(
        db, principal, report_id, payload, context=RequestContext.from_request(request)
    )
