"""Marketplace use cases.

Reading needs ``marketplace:read``; offering material needs ``marketplace:create``; asking for a
listing needs ``marketplace:request``; ``marketplace:manage`` (managers) can act on any listing.
Owners always control their own listings. There is no price, payment or delivery: a request only
tells the owner who is interested, and the owner decides. A published listing lapses after
``MARKETPLACE_LISTING_DAYS`` unless renewed; the daily job ``expire-marketplace-listings``
closes it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    UnprocessableError,
)
from app.integrations.file_storage import FileStorage, StorageError
from app.integrations.file_storage.local import new_storage_key
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.facilities import repository as facilities
from app.modules.marketplace import repository
from app.modules.marketplace.constants import (
    LISTING_TRANSITIONS,
    MAX_PHOTOS_PER_LISTING,
    ListingCategory,
    ListingOutcome,
    ListingStatus,
    RequestStatus,
)
from app.modules.marketplace.models import Listing, ListingPhoto, ListingRequest
from app.modules.marketplace.schemas import (
    CloseRequest,
    ListingCreate,
    ListingOut,
    ListingUpdate,
    PhotoOut,
    PublishRequest,
    RequestCreate,
    RequestOut,
)
from app.modules.notifications import service as notifications
from app.modules.notifications.constants import NotificationCategory
from app.modules.waste_reports.images import normalize_image

MANAGE = "marketplace:manage"
_STORAGE_BACKEND = "local"


class InvalidListingStateError(AppError):
    status_code = 409
    code = "invalid_listing_state"


class RequestExistsError(AppError):
    status_code = 409
    code = "request_exists"


class OwnListingError(AppError):
    status_code = 409
    code = "own_listing"


class ListingExpiredError(AppError):
    status_code = 409
    code = "listing_expired"


class PhotoLimitError(AppError):
    status_code = 409
    code = "photo_limit_reached"


class InvalidRequestStateError(AppError):
    status_code = 409
    code = "invalid_request_state"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _plain(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _can_control(principal: Principal, listing: Listing) -> bool:
    return listing.created_by_id == principal.user_id or principal.has(MANAGE)


def is_expired(listing: Listing, now: dt.datetime) -> bool:
    """A published listing past its expiry. Reserved listings are being handed over: they stay."""
    return (
        listing.status is ListingStatus.PUBLISHED
        and listing.expires_at is not None
        and listing.expires_at <= now
    )


def _visible(principal: Principal, listing: Listing, now: dt.datetime) -> bool:
    on_offer = listing.status is ListingStatus.RESERVED or (
        listing.status is ListingStatus.PUBLISHED and not is_expired(listing, now)
    )
    return on_offer or _can_control(principal, listing)


def _out_many(db: Session, principal: Principal, listings: list[Listing]) -> list[ListingOut]:
    ids = [item.id for item in listings]
    owners = repository.owner_names(db, list({item.created_by_id for item in listings}))
    facility_ids = [item.facility_id for item in listings if item.facility_id is not None]
    facility_names = repository.facility_names(db, list(set(facility_ids)))
    pending = repository.pending_counts(db, ids)
    mine = repository.my_request_statuses(db, ids, principal.user_id)
    photos = repository.photos_for(db, ids)
    now = _now()
    result: list[ListingOut] = []
    for item in listings:
        controls = _can_control(principal, item)
        result.append(
            ListingOut(
                id=item.id,
                title=item.title,
                description=item.description,
                category=item.category,
                quantity=item.quantity,
                unit=item.unit,
                condition=item.condition,
                facility_id=item.facility_id,
                facility_name=facility_names.get(item.facility_id) if item.facility_id else None,
                pickup_city=item.pickup_city,
                status=item.status,
                owner_id=item.created_by_id,
                owner_name=owners.get(item.created_by_id, "Unknown"),
                is_mine=item.created_by_id == principal.user_id,
                pending_request_count=pending.get(item.id, 0) if controls else None,
                my_request_status=mine.get(item.id),
                published_at=item.published_at,
                closed_at=item.closed_at,
                close_reason=item.close_reason,
                outcome=item.outcome,
                expires_at=item.expires_at,
                is_expired=is_expired(item, now),
                photos=[_photo_out(photo) for photo in photos.get(item.id, [])],
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
    return result


def _photo_out(photo: ListingPhoto) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        position=photo.position,
        caption=photo.caption,
        width_px=photo.width_px,
        height_px=photo.height_px,
    )


def _out(db: Session, principal: Principal, listing: Listing) -> ListingOut:
    return _out_many(db, principal, [listing])[0]


def _load_visible(
    db: Session, principal: Principal, listing_id: uuid.UUID, *, for_update: bool = False
) -> Listing:
    listing = repository.get(db, listing_id, for_update=for_update)
    # Drafts and closed listings of other people do not exist as far as the caller can tell.
    if listing is None or not _visible(principal, listing, _now()):
        raise NotFoundError("Listing not found")
    return listing


def _load_controlled(
    db: Session, principal: Principal, listing_id: uuid.UUID, *, for_update: bool = True
) -> Listing:
    listing = _load_visible(db, principal, listing_id, for_update=for_update)
    if not _can_control(principal, listing):
        raise ForbiddenError("Only the owner or a marketplace manager can do this")
    return listing


def _require_facility(db: Session, facility_id: uuid.UUID | None) -> None:
    if facility_id is not None and facilities.get(db, facility_id) is None:
        raise UnprocessableError("facility_id does not refer to a known facility")


def _transition(listing: Listing, target: ListingStatus) -> None:
    if target not in LISTING_TRANSITIONS[listing.status]:
        raise InvalidListingStateError(
            f"A {listing.status.value} listing cannot become {target.value}"
        )
    listing.status = target


def _notify(
    db: Session, recipient_id: uuid.UUID, title: str, listing: Listing, body: str | None = None
) -> None:
    notifications.notify(
        db,
        recipient_id=recipient_id,
        category=NotificationCategory.SYSTEM,
        title=title,
        body=body or listing.title,
        entity_type="marketplace_listing",
        entity_id=listing.id,
    )


# -- listings ------------------------------------------------------------------------------------
def list_listings(
    db: Session,
    principal: Principal,
    params: PageParams,
    *,
    mine: bool,
    category: ListingCategory | None,
    status: ListingStatus | None,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> Page[ListingOut]:
    rows, total = repository.list_page(
        db,
        params,
        now=_now(),
        viewer_id=principal.user_id,
        sees_all=principal.has(MANAGE),
        mine=mine,
        category=category,
        status=status,
        q=q,
        sort_by=sort_by,
        order=order,
    )
    return Page.build(_out_many(db, principal, rows), total, params)


def get_listing(db: Session, principal: Principal, listing_id: uuid.UUID) -> ListingOut:
    return _out(db, principal, _load_visible(db, principal, listing_id))


def create_listing(
    db: Session, principal: Principal, payload: ListingCreate, *, context: RequestContext
) -> ListingOut:
    _require_facility(db, payload.facility_id)
    listing = repository.add(db, created_by_id=principal.user_id, **payload.model_dump())
    audit.record(
        db,
        action="marketplace_listing.created",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        actor_id=principal.user_id,
        context=context,
        changes={
            "category": listing.category.value,
            "quantity": str(listing.quantity),
            "unit": listing.unit.value,
        },
    )
    db.commit()
    db.refresh(listing)
    return _out(db, principal, listing)


def update_listing(
    db: Session,
    principal: Principal,
    listing_id: uuid.UUID,
    payload: ListingUpdate,
    *,
    context: RequestContext,
) -> ListingOut:
    listing = _load_controlled(db, principal, listing_id)
    if listing.status not in (ListingStatus.DRAFT, ListingStatus.PUBLISHED):
        raise InvalidListingStateError(f"A {listing.status.value} listing cannot be edited")
    if "facility_id" in payload.model_fields_set:
        _require_facility(db, payload.facility_id)
    changes: dict[str, Any] = {}
    for field in payload.model_fields_set:
        new = getattr(payload, field)
        old = getattr(listing, field)
        if new == old:
            continue
        changes[field] = {"from": _plain(old), "to": _plain(new)}
        setattr(listing, field, new)
    if changes:
        audit.record(
            db,
            action="marketplace_listing.updated",
            entity_type="marketplace_listing",
            entity_id=listing.id,
            actor_id=principal.user_id,
            context=context,
            changes={"fields": changes},
        )
        db.commit()
        db.refresh(listing)
    return _out(db, principal, listing)


def publish_listing(
    db: Session,
    principal: Principal,
    listing_id: uuid.UUID,
    payload: PublishRequest,
    *,
    default_days: int,
    context: RequestContext,
) -> ListingOut:
    listing = _load_controlled(db, principal, listing_id)
    if listing.status is not ListingStatus.DRAFT:
        raise InvalidListingStateError(f"A {listing.status.value} listing cannot be published")
    _transition(listing, ListingStatus.PUBLISHED)
    now = _now()
    days = payload.duration_days or default_days
    listing.published_at = now
    listing.expires_at = now + dt.timedelta(days=days)
    listing.expiry_notice_sent_at = None
    audit.record(
        db,
        action="marketplace_listing.published",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        actor_id=principal.user_id,
        context=context,
        changes={"duration_days": days, "expires_at": listing.expires_at.isoformat()},
    )
    db.commit()
    db.refresh(listing)
    return _out(db, principal, listing)


def renew_listing(
    db: Session,
    principal: Principal,
    listing_id: uuid.UUID,
    payload: PublishRequest,
    *,
    default_days: int,
    context: RequestContext,
) -> ListingOut:
    """Keep a published listing on offer for another period, counted from now."""
    listing = _load_controlled(db, principal, listing_id)
    if listing.status is not ListingStatus.PUBLISHED:
        raise InvalidListingStateError(f"A {listing.status.value} listing cannot be renewed")
    days = payload.duration_days or default_days
    previous = listing.expires_at
    listing.expires_at = _now() + dt.timedelta(days=days)
    listing.expiry_notice_sent_at = None
    audit.record(
        db,
        action="marketplace_listing.renewed",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        actor_id=principal.user_id,
        context=context,
        changes={
            "duration_days": days,
            "from": previous.isoformat() if previous else None,
            "to": listing.expires_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(listing)
    return _out(db, principal, listing)


def close_listing(
    db: Session,
    principal: Principal,
    listing_id: uuid.UUID,
    payload: CloseRequest,
    *,
    context: RequestContext,
) -> ListingOut:
    listing = _load_controlled(db, principal, listing_id)
    outcome = payload.outcome or ListingOutcome.WITHDRAWN
    if outcome is ListingOutcome.HANDED_OVER and listing.status is not ListingStatus.RESERVED:
        raise InvalidListingStateError(
            "Only a reserved listing (one with an accepted request) can be marked as handed over"
        )
    _transition(listing, ListingStatus.CLOSED)
    listing.closed_at = _now()
    listing.close_reason = payload.reason
    listing.outcome = outcome
    declined: list[str] = []
    for request in repository.pending_requests(db, listing.id):
        request.status = RequestStatus.DECLINED
        request.decided_at = listing.closed_at
        declined.append(str(request.id))
        _notify(db, request.requester_id, "A listing you asked for was closed", listing)
    accepted = repository.accepted_request(db, listing.id)
    if accepted is not None:
        _notify(
            db,
            accepted.requester_id,
            "The hand-over was recorded as complete"
            if outcome is ListingOutcome.HANDED_OVER
            else "A listing reserved for you was withdrawn",
            listing,
        )
    audit.record(
        db,
        action="marketplace_listing.closed",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        actor_id=principal.user_id,
        context=context,
        changes={
            "reason": payload.reason,
            "outcome": outcome.value,
            "declined_requests": declined,
        },
    )
    db.commit()
    db.refresh(listing)
    return _out(db, principal, listing)


# -- requests ------------------------------------------------------------------------------------
def _request_out(
    principal: Principal,
    request: ListingRequest,
    listing: Listing,
    contacts: dict[uuid.UUID, tuple[str, str]],
) -> RequestOut:
    name, email = contacts.get(request.requester_id, ("Unknown", ""))
    shows_email = _can_control(principal, listing) or request.requester_id == principal.user_id
    return RequestOut(
        id=request.id,
        listing_id=request.listing_id,
        listing_title=listing.title,
        requester_id=request.requester_id,
        requester_name=name,
        requester_email=email if shows_email else None,
        message=request.message,
        status=request.status,
        created_at=request.created_at,
        decided_at=request.decided_at,
    )


def create_request(
    db: Session,
    principal: Principal,
    listing_id: uuid.UUID,
    payload: RequestCreate,
    *,
    context: RequestContext,
) -> RequestOut:
    listing = _load_visible(db, principal, listing_id, for_update=True)
    if listing.created_by_id == principal.user_id:
        raise OwnListingError("You cannot request your own listing")
    if listing.status is not ListingStatus.PUBLISHED:
        raise InvalidListingStateError("Only published listings can be requested")
    if is_expired(listing, _now()):
        raise ListingExpiredError("This listing has expired and can no longer be requested")
    existing = repository.get_request_for(db, listing.id, principal.user_id)
    if existing is not None and existing.status is not RequestStatus.WITHDRAWN:
        raise RequestExistsError("You already have a request for this listing")
    if existing is None:
        request = repository.add_request(
            db,
            listing_id=listing.id,
            requester_id=principal.user_id,
            message=payload.message,
        )
    else:
        # A withdrawn request is simply asked again (the pair is unique).
        request = existing
        request.status = RequestStatus.PENDING
        request.message = payload.message
        request.decided_at = None
    audit.record(
        db,
        action="marketplace_request.created",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        actor_id=principal.user_id,
        context=context,
        changes={"request_id": str(request.id)},
    )
    _notify(db, listing.created_by_id, "Someone asked for your listing", listing)
    db.commit()
    db.refresh(request)
    contacts = repository.user_contacts(db, [request.requester_id])
    return _request_out(principal, request, listing, contacts)


def list_requests(db: Session, principal: Principal, listing_id: uuid.UUID) -> list[RequestOut]:
    listing = _load_controlled(db, principal, listing_id, for_update=False)
    rows = repository.requests_for_listing(db, listing.id)
    contacts = repository.user_contacts(db, list({r.requester_id for r in rows}))
    return [_request_out(principal, r, listing, contacts) for r in rows]


def my_requests(db: Session, principal: Principal, params: PageParams) -> Page[RequestOut]:
    rows, total = repository.requests_by_user(db, params, principal.user_id)
    titles = repository.listing_titles(db, list({r.listing_id for r in rows}))
    contacts = repository.user_contacts(db, [principal.user_id])
    items: list[RequestOut] = []
    for r in rows:
        name, email = contacts.get(r.requester_id, ("Unknown", ""))
        items.append(
            RequestOut(
                id=r.id,
                listing_id=r.listing_id,
                listing_title=titles.get(r.listing_id, "Unknown"),
                requester_id=r.requester_id,
                requester_name=name,
                requester_email=email,
                message=r.message,
                status=r.status,
                created_at=r.created_at,
                decided_at=r.decided_at,
            )
        )
    return Page.build(items, total, params)


def _load_request(db: Session, request_id: uuid.UUID) -> tuple[ListingRequest, Listing]:
    request = repository.get_request(db, request_id)
    listing = repository.get(db, request.listing_id, for_update=True) if request else None
    if request is None or listing is None:
        raise NotFoundError("Request not found")
    # Lock the request row too, now that the listing lock serialises competing decisions.
    request = repository.get_request(db, request_id, for_update=True) or request
    return request, listing


def accept_request(
    db: Session, principal: Principal, request_id: uuid.UUID, *, context: RequestContext
) -> RequestOut:
    request, listing = _load_request(db, request_id)
    if not _can_control(principal, listing):
        # Same answer as an unknown id: do not confirm that someone else's request exists.
        raise NotFoundError("Request not found")
    if request.status is not RequestStatus.PENDING:
        raise InvalidRequestStateError(f"A {request.status.value} request cannot be accepted")
    _transition(listing, ListingStatus.RESERVED)
    now = _now()
    request.status = RequestStatus.ACCEPTED
    request.decided_at = now
    for other in repository.pending_requests(db, listing.id):
        if other.id == request.id:
            continue
        other.status = RequestStatus.DECLINED
        other.decided_at = now
        _notify(
            db, other.requester_id, "A listing you asked for was reserved for someone else", listing
        )
    _notify(db, request.requester_id, "Your request was accepted", listing)
    audit.record(
        db,
        action="marketplace_request.accepted",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        actor_id=principal.user_id,
        context=context,
        changes={"request_id": str(request.id)},
    )
    db.commit()
    db.refresh(request)
    contacts = repository.user_contacts(db, [request.requester_id])
    return _request_out(principal, request, listing, contacts)


def decline_request(
    db: Session, principal: Principal, request_id: uuid.UUID, *, context: RequestContext
) -> RequestOut:
    """Decline a pending request, or release an accepted one (the listing is offered again)."""
    request, listing = _load_request(db, request_id)
    if not _can_control(principal, listing):
        raise NotFoundError("Request not found")
    if request.status not in (RequestStatus.PENDING, RequestStatus.ACCEPTED):
        raise InvalidRequestStateError(f"A {request.status.value} request cannot be declined")
    released = request.status is RequestStatus.ACCEPTED
    request.status = RequestStatus.DECLINED
    request.decided_at = _now()
    if released and listing.status is ListingStatus.RESERVED:
        _transition(listing, ListingStatus.PUBLISHED)
    _notify(db, request.requester_id, "Your request was declined", listing)
    audit.record(
        db,
        action="marketplace_request.declined",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        actor_id=principal.user_id,
        context=context,
        changes={"request_id": str(request.id), "released_reservation": released},
    )
    db.commit()
    db.refresh(request)
    contacts = repository.user_contacts(db, [request.requester_id])
    return _request_out(principal, request, listing, contacts)


def withdraw_request(
    db: Session, principal: Principal, request_id: uuid.UUID, *, context: RequestContext
) -> RequestOut:
    request, listing = _load_request(db, request_id)
    if request.requester_id != principal.user_id:
        raise NotFoundError("Request not found")
    if request.status not in (RequestStatus.PENDING, RequestStatus.ACCEPTED):
        raise InvalidRequestStateError(f"A {request.status.value} request cannot be withdrawn")
    released = request.status is RequestStatus.ACCEPTED
    request.status = RequestStatus.WITHDRAWN
    request.decided_at = _now()
    if released and listing.status is ListingStatus.RESERVED:
        _transition(listing, ListingStatus.PUBLISHED)
    _notify(db, listing.created_by_id, "A request for your listing was withdrawn", listing)
    audit.record(
        db,
        action="marketplace_request.withdrawn",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        actor_id=principal.user_id,
        context=context,
        changes={"request_id": str(request.id), "released_reservation": released},
    )
    db.commit()
    db.refresh(request)
    contacts = repository.user_contacts(db, [request.requester_id])
    return _request_out(principal, request, listing, contacts)


# -- photos --------------------------------------------------------------------------------------
def upload_photo(
    db: Session,
    storage: FileStorage,
    principal: Principal,
    listing_id: uuid.UUID,
    data: bytes,
    *,
    caption: str | None,
    max_bytes: int,
    context: RequestContext,
) -> PhotoOut:
    """Attach a photo. It is decoded and re-encoded, so EXIF (including GPS) never survives."""
    if len(data) > max_bytes:
        raise PayloadTooLargeError(f"The file is larger than the {max_bytes}-byte limit")
    listing = _load_controlled(db, principal, listing_id)  # locks the listing row
    if listing.status not in (ListingStatus.DRAFT, ListingStatus.PUBLISHED):
        raise InvalidListingStateError(
            f"Photos of a {listing.status.value} listing cannot be changed"
        )
    count, highest = repository.photo_stats(db, listing.id)
    if count >= MAX_PHOTOS_PER_LISTING:
        raise PhotoLimitError(f"A listing can have at most {MAX_PHOTOS_PER_LISTING} photos")
    image = normalize_image(data)
    key = new_storage_key(image.extension)
    try:
        storage.save(key, image.content)
    except StorageError as exc:
        raise AppError("The file could not be stored") from exc
    try:
        photo = repository.add_photo(
            db,
            listing_id=listing.id,
            uploaded_by_id=principal.user_id,
            position=highest + 1,
            caption=caption,
            storage_backend=_STORAGE_BACKEND,
            storage_key=key,
            content_type=image.content_type,
            size_bytes=len(image.content),
            sha256=hashlib.sha256(image.content).hexdigest(),
            width_px=image.width,
            height_px=image.height,
        )
        audit.record(
            db,
            action="marketplace_listing.photo_added",
            entity_type="marketplace_listing",
            entity_id=listing.id,
            actor_id=principal.user_id,
            context=context,
            changes={
                "photo_id": str(photo.id),
                "content_type": image.content_type,
                "size_bytes": len(image.content),
            },
        )
        db.commit()
    except BaseException:
        db.rollback()
        storage.delete(key)  # no file without a row
        raise
    return _photo_out(photo)


def delete_photo(
    db: Session,
    storage: FileStorage,
    principal: Principal,
    listing_id: uuid.UUID,
    photo_id: uuid.UUID,
    *,
    context: RequestContext,
) -> None:
    listing = _load_controlled(db, principal, listing_id)
    if listing.status not in (ListingStatus.DRAFT, ListingStatus.PUBLISHED):
        raise InvalidListingStateError(
            f"Photos of a {listing.status.value} listing cannot be changed"
        )
    photo = repository.get_photo(db, photo_id)
    if photo is None or photo.listing_id != listing.id:
        raise NotFoundError("Photo not found")
    key = photo.storage_key
    db.delete(photo)
    audit.record(
        db,
        action="marketplace_listing.photo_removed",
        entity_type="marketplace_listing",
        entity_id=listing.id,
        actor_id=principal.user_id,
        context=context,
        changes={"photo_id": str(photo_id)},
    )
    db.commit()
    storage.delete(
        key
    )  # after the commit: a failed delete leaves an orphan file, never a dead link


def read_photo(
    db: Session, storage: FileStorage, principal: Principal, photo_id: uuid.UUID
) -> tuple[bytes, ListingPhoto]:
    photo = repository.get_photo(db, photo_id)
    listing = repository.get(db, photo.listing_id) if photo is not None else None
    # Same answer as for the listing itself: photos of drafts and lapsed listings do not exist.
    if photo is None or listing is None or not _visible(principal, listing, _now()):
        raise NotFoundError("Photo not found")
    try:
        return storage.read(photo.storage_key), photo
    except StorageError as exc:
        raise AppError("The file is currently unavailable") from exc
