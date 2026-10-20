"""Request and response bodies of the marketplace API."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.marketplace.constants import (
    ListingCategory,
    ListingCondition,
    ListingStatus,
    ListingUnit,
    RequestStatus,
)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
City = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
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


class CloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason | None = None


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
