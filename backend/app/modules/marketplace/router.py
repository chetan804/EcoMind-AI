"""Marketplace endpoints, mounted at ``/api/v1/marketplace``."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request, Response, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import AppSettings, DbSession
from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams, page_params
from app.core.exceptions import PayloadTooLargeError
from app.integrations.file_storage import FileStorage, LocalFileStorage
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.marketplace import service
from app.modules.marketplace.constants import ListingCategory, ListingStatus
from app.modules.marketplace.schemas import (
    CloseRequest,
    ListingCreate,
    ListingOut,
    ListingUpdate,
    PhotoOut,
    PublishRequest,
    RequestCreate,
    RequestOut,
    SortField,
)

router = APIRouter()

CanRead = Annotated[Principal, Depends(require_permissions("marketplace:read"))]
CanCreate = Annotated[Principal, Depends(require_permissions("marketplace:create"))]
CanRequest = Annotated[Principal, Depends(require_permissions("marketplace:request"))]
Pagination = Annotated[PageParams, Depends(page_params)]


def get_storage(settings: AppSettings) -> FileStorage:
    return LocalFileStorage(settings.file_storage_local_path)


Storage = Annotated[FileStorage, Depends(get_storage)]


@router.get("/listings", response_model=Page[ListingOut])
def list_listings(
    db: DbSession,
    principal: CanRead,
    params: Pagination,
    mine: bool = False,
    category: ListingCategory | None = None,
    status: ListingStatus | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Search title, text, city")] = None,
    sort_by: SortField = "created_at",
    order: SortOrder = SortOrder.DESC,
) -> Page[ListingOut]:
    return service.list_listings(
        db,
        principal,
        params,
        mine=mine,
        category=category,
        status=status,
        q=q,
        sort_by=sort_by,
        order=order,
    )


@router.post("/listings", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(
    payload: ListingCreate, request: Request, db: DbSession, principal: CanCreate
) -> ListingOut:
    """Create a draft listing owned by the caller."""
    return service.create_listing(
        db, principal, payload, context=RequestContext.from_request(request)
    )


@router.get("/requests/mine", response_model=Page[RequestOut])
def my_requests(db: DbSession, principal: CanRequest, params: Pagination) -> Page[RequestOut]:
    return service.my_requests(db, principal, params)


@router.post("/requests/{request_id}/accept", response_model=RequestOut)
def accept_request(
    request_id: uuid.UUID, request: Request, db: DbSession, principal: CanRead
) -> RequestOut:
    """Owner or manager: accept a pending request. The listing becomes reserved."""
    return service.accept_request(
        db, principal, request_id, context=RequestContext.from_request(request)
    )


@router.post("/requests/{request_id}/decline", response_model=RequestOut)
def decline_request(
    request_id: uuid.UUID, request: Request, db: DbSession, principal: CanRead
) -> RequestOut:
    """Owner or manager: decline a pending request, or release an accepted one."""
    return service.decline_request(
        db, principal, request_id, context=RequestContext.from_request(request)
    )


@router.post("/requests/{request_id}/withdraw", response_model=RequestOut)
def withdraw_request(
    request_id: uuid.UUID, request: Request, db: DbSession, principal: CanRequest
) -> RequestOut:
    """The requester withdraws their own pending or accepted request."""
    return service.withdraw_request(
        db, principal, request_id, context=RequestContext.from_request(request)
    )


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: uuid.UUID, db: DbSession, principal: CanRead) -> ListingOut:
    return service.get_listing(db, principal, listing_id)


@router.patch("/listings/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: uuid.UUID,
    payload: ListingUpdate,
    request: Request,
    db: DbSession,
    principal: CanRead,
) -> ListingOut:
    """Owner or manager. Only draft and published listings can be edited."""
    return service.update_listing(
        db, principal, listing_id, payload, context=RequestContext.from_request(request)
    )


@router.post("/listings/{listing_id}/publish", response_model=ListingOut)
def publish_listing(
    listing_id: uuid.UUID,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    principal: CanRead,
    payload: Annotated[PublishRequest, Body(default_factory=PublishRequest)],
) -> ListingOut:
    """Put a draft on offer. It lapses after ``duration_days`` (default: the server setting)."""
    return service.publish_listing(
        db,
        principal,
        listing_id,
        payload,
        default_days=settings.marketplace_listing_days,
        context=RequestContext.from_request(request),
    )


@router.post("/listings/{listing_id}/renew", response_model=ListingOut)
def renew_listing(
    listing_id: uuid.UUID,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    principal: CanRead,
    payload: Annotated[PublishRequest, Body(default_factory=PublishRequest)],
) -> ListingOut:
    """Owner or manager: keep a published listing on offer for another period."""
    return service.renew_listing(
        db,
        principal,
        listing_id,
        payload,
        default_days=settings.marketplace_listing_days,
        context=RequestContext.from_request(request),
    )


@router.post("/listings/{listing_id}/close", response_model=ListingOut)
def close_listing(
    listing_id: uuid.UUID,
    request: Request,
    db: DbSession,
    principal: CanRead,
    payload: Annotated[CloseRequest, Body(default_factory=CloseRequest)],
) -> ListingOut:
    """Withdraw or complete a listing. Pending requests are declined."""
    return service.close_listing(
        db, principal, listing_id, payload, context=RequestContext.from_request(request)
    )


@router.get("/listings/{listing_id}/requests", response_model=list[RequestOut])
def list_requests(listing_id: uuid.UUID, db: DbSession, principal: CanRead) -> list[RequestOut]:
    """Owner or manager: who asked for this listing."""
    return service.list_requests(db, principal, listing_id)


@router.post(
    "/listings/{listing_id}/requests",
    response_model=RequestOut,
    status_code=status.HTTP_201_CREATED,
)
def create_request(
    listing_id: uuid.UUID,
    payload: RequestCreate,
    request: Request,
    db: DbSession,
    principal: CanRequest,
) -> RequestOut:
    return service.create_request(
        db, principal, listing_id, payload, context=RequestContext.from_request(request)
    )


@router.post(
    "/listings/{listing_id}/photos", response_model=PhotoOut, status_code=status.HTTP_201_CREATED
)
async def upload_photo(
    listing_id: uuid.UUID,
    request: Request,
    db: DbSession,
    storage: Storage,
    settings: AppSettings,
    principal: CanRead,
    caption: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> PhotoOut:
    """Owner or manager: attach one photo (raw request body: JPEG, PNG or WebP; at most 4).

    The size limit is enforced while streaming. The image is validated and re-encoded, which
    removes EXIF/GPS metadata.
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
        service.upload_photo,
        db,
        storage,
        principal,
        listing_id,
        b"".join(chunks),
        caption=caption.strip() if caption else None,
        max_bytes=limit,
        context=RequestContext.from_request(request),
    )


@router.delete("/listings/{listing_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(
    listing_id: uuid.UUID,
    photo_id: uuid.UUID,
    request: Request,
    db: DbSession,
    storage: Storage,
    principal: CanRead,
) -> Response:
    service.delete_photo(
        db,
        storage,
        principal,
        listing_id,
        photo_id,
        context=RequestContext.from_request(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/photos/{photo_id}/content")
def photo_content(
    photo_id: uuid.UUID, db: DbSession, storage: Storage, principal: CanRead
) -> Response:
    data, photo = service.read_photo(db, storage, principal, photo_id)
    extension = photo.storage_key.rsplit(".", 1)[-1]
    return Response(
        content=data,
        media_type=photo.content_type,
        headers={
            "Content-Disposition": f'inline; filename="photo-{photo.id}.{extension}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-cache",
        },
    )
