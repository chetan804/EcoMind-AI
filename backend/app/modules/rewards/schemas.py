"""Request and response bodies of the rewards API."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.rewards.constants import (
    MAX_ITEM_COST,
    LedgerEntryType,
    LedgerSourceType,
    RedemptionStatus,
)

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]

BASIS = (
    "Points come from verified collected weight only (configured points per kilogram). Impact is "
    "the weight in kilograms; no carbon or other environmental coefficient is applied because "
    "none is sourced. Entries are append-only: corrections are reversals or adjustments."
)


class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    entry_type: LedgerEntryType
    points: int
    impact_weight_kg: decimal.Decimal | None
    source_type: LedgerSourceType
    source_id: uuid.UUID | None
    reverses_entry_id: uuid.UUID | None
    created_by_id: uuid.UUID | None
    description: str | None
    created_at: dt.datetime


class Balance(BaseModel):
    user_id: uuid.UUID
    points: int = Field(description="Sum of all entries (signed)")
    earned_points: int
    impact_weight_kg: decimal.Decimal = Field(description="Earned weight minus reversed weight")
    entries: int
    points_per_kg: int
    basis: str = BASIS


class LedgerSummary(BaseModel):
    entries: int
    users: int
    points_issued: int = Field(description="Sum of positive entries")
    points_removed: int = Field(description="Sum of negative entries, as a positive number")
    net_points: int
    impact_weight_kg: decimal.Decimal
    basis: str = BASIS


class AdjustmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    points: int = Field(ge=-100_000, le=100_000)
    description: Reason

    @model_validator(mode="after")
    def _non_zero(self) -> Self:
        if self.points == 0:
            raise ValueError("points must not be zero")
        return self


class ReverseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


# -- catalogue and redemptions -----------------------------------------------------------------
ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
ItemText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
OptionalReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Cost = Annotated[int, Field(ge=1, le=MAX_ITEM_COST)]
Stock = Annotated[int, Field(ge=0, le=1_000_000)]
PerUser = Annotated[int, Field(ge=1, le=1000)]


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("valid_until must include a time zone (for example 2026-12-31T23:59:00Z)")
    return value


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ItemName
    description: ItemText | None = None
    points_cost: Cost
    stock: Stock | None = Field(default=None, description="Units left; null means unlimited")
    max_per_user: PerUser | None = None
    active: bool = True
    valid_until: dt.datetime | None = None

    @model_validator(mode="after")
    def _timezone(self) -> Self:
        _aware(self.valid_until)
        return self


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ItemName | None = None
    description: ItemText | None = None
    points_cost: Cost | None = None
    stock: Stock | None = None
    max_per_user: PerUser | None = None
    active: bool | None = None
    valid_until: dt.datetime | None = None

    @model_validator(mode="after")
    def _checks(self) -> Self:
        for field in ("name", "points_cost", "active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        _aware(self.valid_until)
        return self


class ItemOut(BaseModel):
    """Staff view of a catalogue item."""

    id: uuid.UUID
    name: str
    description: str | None
    points_cost: int
    stock: int | None
    max_per_user: int | None
    active: bool
    valid_until: dt.datetime | None
    redeemed_count: int = Field(description="Redemptions that are pending or fulfilled")
    pending_count: int = Field(description="Redeemed, not yet handed over")
    created_at: dt.datetime
    updated_at: dt.datetime


class CatalogItemOut(BaseModel):
    """What a citizen sees: only offers that are active and not expired."""

    id: uuid.UUID
    name: str
    description: str | None
    points_cost: int
    stock_remaining: int | None
    valid_until: dt.datetime | None
    remaining_for_you: int | None = Field(description="Null when there is no per-person limit")
    available: bool
    unavailable_reason: Literal["out_of_stock", "limit_reached"] | None


class RedeemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_request_id: uuid.UUID = Field(
        description="Chosen by the client once per attempt; repeating it cannot spend points twice"
    )


class RedemptionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    # Only for staff, who need to know who to hand the reward to.
    user_name: str | None
    user_email: str | None
    item_id: uuid.UUID
    item_name: str
    points_spent: int
    code: str
    status: RedemptionStatus
    created_at: dt.datetime
    fulfilled_at: dt.datetime | None
    note: str | None
    cancelled_at: dt.datetime | None
    cancel_reason: str | None


class FulfilRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: OptionalReason | None = None


class CancelOwnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: OptionalReason | None = None
