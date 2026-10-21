"""Request and response bodies of the marketplace API."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.marketplace.constants import (
    MAX_LISTING_DAYS,
    ListingCategory,
    ListingCondition,
    ListingOutcome,
    ListingStatus,
    ListingUnit,
    RequestStatus,
)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
City = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Caption = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Days = Annotated[int, Field(ge=1, le=MAX_LISTING_DAYS)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Quantity = Annotated[decimal.Decimal, Field(gt=0, le=1_000_000_000, decimal_places=3)]

SortField = Literal["created_at", "title", "quantity"]


class ListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Text | None = None
    category: ListingCategory
    quantity: Quantity
    unit: ListingUnit
    condition: ListingCondition
    facility_id: uuid.UUID | None = None
    pickup_city: City | None = None


class ListingUpdate(BaseModel):
    """Partial update, allowed while the listing is a draft or published."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Text | None = None
    category: ListingCategory | None = None
    quantity: Quantity | None = None
    unit: ListingUnit | None = None
    condition: ListingCondition | None = None
    facility_id: uuid.UUID | None = None
    pickup_city: City | None = None

    @model_validator(mode="after")
    def _required_fields_cannot_be_cleared(self) -> Self:
        for field in ("title", "category", "quantity", "unit", "condition"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PublishRequest(BaseModel):
    """Optional: how long the listing stays on offer (default: ``MARKETPLACE_LISTING_DAYS``)."""

    model_config = ConfigDict(extra="forbid")

    duration_days: Days | None = None


class CloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason | None = None
    # ``handed_over`` is allowed only on a reserved listing. Omitted means ``withdrawn``;
    # ``expired`` is set only by the expiry job.
    outcome: Literal[ListingOutcome.HANDED_OVER, ListingOutcome.WITHDRAWN] | None = None


class PhotoOut(BaseModel):
    """Fetch the image from ``GET /marketplace/photos/{id}/content`` (needs the access token)."""

    id: uuid.UUID
    position: int
    caption: str | None
    width_px: int
    height_px: int


class ListingOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    category: ListingCategory
    quantity: decimal.Decimal
    unit: ListingUnit
    condition: ListingCondition
    facility_id: uuid.UUID | None
    facility_name: str | None
    pickup_city: str | None
    status: ListingStatus
    owner_id: uuid.UUID
    owner_name: str
    is_mine: bool
    # Only for the owner and for marketplace managers; ``None`` for everyone else.
    pending_request_count: int | None
    # The caller's own request on this listing, if any.
    my_request_status: RequestStatus | None
    published_at: dt.datetime | None
    closed_at: dt.datetime | None
    close_reason: str | None
    outcome: ListingOutcome | None
    # When a published listing lapses. ``is_expired`` is true between that moment and the next run
    # of the expiry job; such a listing cannot be requested and is hidden from other people.
    expires_at: dt.datetime | None
    is_expired: bool
    photos: list[PhotoOut]
    created_at: dt.datetime
    updated_at: dt.datetime


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Text | None = None


class RequestOut(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    listing_title: str
    requester_id: uuid.UUID
    requester_name: str
    # Contact address: shown only to the listing owner and to managers, and to the requester.
    requester_email: str | None
    message: str | None
    status: RequestStatus
    created_at: dt.datetime
    decided_at: dt.datetime | None
