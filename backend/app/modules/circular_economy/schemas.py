"""Request and response bodies of the recovery-records API."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.circular_economy.constants import RecoveryMethod, VerificationStatus

Weight = Annotated[decimal.Decimal, Field(ge=0, le=1_000_000_000, decimal_places=3)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
SortField = Literal["processed_at", "created_at", "input_weight_kg", "recovered_weight_kg"]

BASIS = (
    "Only verified records are counted. Recovery rate = recovered weight / input weight as "
    "recorded by facility staff and verified by a second person. It is a mass ratio, not a "
    "landfill-diversion, carbon or environmental-benefit claim."
)


class RecoveryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility_id: uuid.UUID
    material_category_id: uuid.UUID
    collection_task_id: uuid.UUID | None = Field(
        default=None, description="Completed collection task the material came from"
    )
    evidence_media_asset_id: uuid.UUID | None = None
    recovery_method: RecoveryMethod
    input_weight_kg: Weight
    recovered_weight_kg: Weight
    processed_at: dt.datetime
    notes: Note | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.input_weight_kg <= 0:
            raise ValueError("input_weight_kg must be greater than zero")
        if self.recovered_weight_kg > self.input_weight_kg:
            raise ValueError("recovered_weight_kg cannot exceed input_weight_kg")
        if self.processed_at.tzinfo is None:
            raise ValueError("processed_at must include a timezone offset")
        return self


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["verified", "rejected"]
    notes: Note | None = None

    @model_validator(mode="after")
    def _reason_for_rejection(self) -> Self:
        if self.decision == "rejected" and not self.notes:
            raise ValueError("notes are required when rejecting a record")
        return self


class RecoveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    facility_id: uuid.UUID
    material_category_id: uuid.UUID
    collection_task_id: uuid.UUID | None
    evidence_media_asset_id: uuid.UUID | None
    recovery_method: RecoveryMethod
    input_weight_kg: decimal.Decimal
    recovered_weight_kg: decimal.Decimal
    processed_at: dt.datetime
    created_by_id: uuid.UUID
    verification_status: VerificationStatus
    verified_by_id: uuid.UUID | None
    verified_at: dt.datetime | None
    notes: str | None
    created_at: dt.datetime


class Breakdown(BaseModel):
    key: str
    label: str
    records: int
    input_weight_kg: decimal.Decimal
    recovered_weight_kg: decimal.Decimal
    recovery_rate: decimal.Decimal | None


class RecoverySummary(BaseModel):
    verified_records: int
    input_weight_kg: decimal.Decimal
    recovered_weight_kg: decimal.Decimal
    recovery_rate: decimal.Decimal | None
    pending_records: int = Field(description="Not counted until verified")
    rejected_records: int = Field(description="Never counted")
    by_category: list[Breakdown]
    by_method: list[Breakdown]
    basis: str = BASIS
