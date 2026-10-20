from __future__ import annotations

from enum import StrEnum


class ListingCategory(StrEnum):
    PLASTICS = "plastics"
    METALS = "metals"
    PAPER = "paper"
    GLASS = "glass"
    E_WASTE = "e_waste"
    ORGANICS = "organics"
    TEXTILES = "textiles"
    WOOD = "wood"
    FURNITURE = "furniture"
    OTHER = "other"


class ListingUnit(StrEnum):
    KG = "kg"
    UNITS = "units"


class ListingCondition(StrEnum):
    LIKE_NEW = "like_new"
    GOOD = "good"
    FAIR = "fair"
    DAMAGED = "damaged"


class ListingStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RESERVED = "reserved"
    CLOSED = "closed"


class RequestStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


# Listing lifecycle. ``reserved`` is entered only by accepting a request and left only by
# releasing it (or by closing the listing); nothing else moves a listing in or out of it.
LISTING_TRANSITIONS: dict[ListingStatus, frozenset[ListingStatus]] = {
    ListingStatus.DRAFT: frozenset({ListingStatus.PUBLISHED, ListingStatus.CLOSED}),
    ListingStatus.PUBLISHED: frozenset({ListingStatus.RESERVED, ListingStatus.CLOSED}),
    ListingStatus.RESERVED: frozenset({ListingStatus.PUBLISHED, ListingStatus.CLOSED}),
    ListingStatus.CLOSED: frozenset(),
}
