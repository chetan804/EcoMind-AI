"""Database access for the marketplace. No business rules and no commits here."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.enums import SortOrder
from app.common.pagination import PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.modules.facilities.models import Facility
from app.modules.marketplace.constants import ListingCategory, ListingStatus, RequestStatus
from app.modules.marketplace.models import Listing, ListingRequest
from app.modules.users.models import User

_SORT: dict[str, SQLColumnExpression[Any]] = {
    "created_at": Listing.created_at,
    "title": func.lower(Listing.title),
    "quantity": Listing.quantity,
}


def get(db: Session, listing_id: uuid.UUID, *, for_update: bool = False) -> Listing | None:
    stmt = select(Listing).where(Listing.id == listing_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def add(db: Session, **fields: object) -> Listing:
    listing = Listing(**fields)
    db.add(listing)
    db.flush()
    return listing


def list_page(
    db: Session,
    params: PageParams,
    *,
    viewer_id: uuid.UUID,
    sees_all: bool,
    mine: bool,
    category: ListingCategory | None,
    status: ListingStatus | None,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> tuple[list[Listing], int]:
    stmt = select(Listing)
    if mine:
        stmt = stmt.where(Listing.created_by_id == viewer_id)
    elif not sees_all:
        # Everyone else sees what is on offer, plus every listing of their own.
        stmt = stmt.where(
            or_(
                Listing.status.in_([ListingStatus.PUBLISHED, ListingStatus.RESERVED]),
                Listing.created_by_id == viewer_id,
            )
        )
    if category is not None:
        stmt = stmt.where(Listing.category == category)
    if status is not None:
        stmt = stmt.where(Listing.status == status)
    pattern = contains_pattern(q) if q else None
    if pattern is not None:
        stmt = stmt.where(
            or_(
                Listing.title.ilike(pattern, escape=LIKE_ESCAPE),
                Listing.description.ilike(pattern, escape=LIKE_ESCAPE),
                Listing.pickup_city.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _SORT[sort_by]
    direction = column.desc() if order is SortOrder.DESC else column.asc()
    page = stmt.order_by(direction, Listing.id).limit(params.limit).offset(params.offset)
    return list(db.execute(page).scalars()), total


def owner_names(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all()
    return {uid: name for uid, name in rows}


def facility_names(db: Session, facility_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not facility_ids:
        return {}
    rows = db.execute(select(Facility.id, Facility.name).where(Facility.id.in_(facility_ids))).all()
    return {fid: name for fid, name in rows}


def pending_counts(db: Session, listing_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not listing_ids:
        return {}
    rows = db.execute(
        select(ListingRequest.listing_id, func.count())
        .where(
            ListingRequest.listing_id.in_(listing_ids),
            ListingRequest.status == RequestStatus.PENDING,
        )
        .group_by(ListingRequest.listing_id)
    ).all()
    return {lid: count for lid, count in rows}


def my_request_statuses(
    db: Session, listing_ids: list[uuid.UUID], user_id: uuid.UUID
) -> dict[uuid.UUID, RequestStatus]:
    if not listing_ids:
        return {}
    rows = db.execute(
        select(ListingRequest.listing_id, ListingRequest.status).where(
            ListingRequest.listing_id.in_(listing_ids), ListingRequest.requester_id == user_id
        )
    ).all()
    return {lid: status for lid, status in rows}


# -- requests ------------------------------------------------------------------------------------
def get_request(
    db: Session, request_id: uuid.UUID, *, for_update: bool = False
) -> ListingRequest | None:
    stmt = select(ListingRequest).where(ListingRequest.id == request_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def get_request_for(
    db: Session, listing_id: uuid.UUID, requester_id: uuid.UUID
) -> ListingRequest | None:
    return db.execute(
        select(ListingRequest).where(
            ListingRequest.listing_id == listing_id, ListingRequest.requester_id == requester_id
        )
    ).scalar_one_or_none()


def add_request(db: Session, **fields: object) -> ListingRequest:
    request = ListingRequest(**fields)
    db.add(request)
    db.flush()
    return request


def requests_for_listing(db: Session, listing_id: uuid.UUID) -> list[ListingRequest]:
    stmt = (
        select(ListingRequest)
        .where(ListingRequest.listing_id == listing_id)
        .order_by(ListingRequest.created_at, ListingRequest.id)
    )
    return list(db.execute(stmt).scalars())


def requests_by_user(
    db: Session, params: PageParams, requester_id: uuid.UUID
) -> tuple[list[ListingRequest], int]:
    stmt = select(ListingRequest).where(ListingRequest.requester_id == requester_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    page = (
        stmt.order_by(ListingRequest.created_at.desc(), ListingRequest.id)
        .limit(params.limit)
        .offset(params.offset)
    )
    return list(db.execute(page).scalars()), total


def pending_requests(db: Session, listing_id: uuid.UUID) -> list[ListingRequest]:
    stmt = (
        select(ListingRequest)
        .where(
            ListingRequest.listing_id == listing_id,
            ListingRequest.status == RequestStatus.PENDING,
        )
        .with_for_update()
    )
    return list(db.execute(stmt).scalars())


def listing_titles(db: Session, listing_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not listing_ids:
        return {}
    rows = db.execute(select(Listing.id, Listing.title).where(Listing.id.in_(listing_ids))).all()
    return {lid: title for lid, title in rows}


def user_contacts(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[str, str]]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(User.id, User.full_name, User.email).where(User.id.in_(user_ids))
    ).all()
    return {uid: (name, email) for uid, name, email in rows}
