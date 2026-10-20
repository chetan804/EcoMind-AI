"""Request and response bodies of the rewards API."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.rewards.constants import LedgerEntryType, LedgerSourceType

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
