"""Request and response bodies of the material-passport API."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.material_passports.constants import CustodyEventType, PassportStatus

Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
Weight = Annotated[decimal.Decimal, Field(gt=0, le=1_000_000_000, decimal_places=3)]
SortField = Literal["created_at", "weight_kg", "passport_code", "status"]


class PassportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_category_id: uuid.UUID
    weight_kg: Weight
    description: Note | None = None
    origin_collection_task_id: uuid.UUID | None = Field(
        default=None, description="Completed collection task the batch came from"
    )
    current_facility_id: uuid.UUID | None = Field(
        default=None, description="Facility currently holding the batch"
    )


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: CustodyEventType
    from_facility_id: uuid.UUID | None = None
    to_facility_id: uuid.UUID | None = None
    occurred_at: dt.datetime | None = Field(default=None, description="Defaults to now")
    notes: Note | None = None


class LinkRecovery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovery_record_id: uuid.UUID


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    event_type: CustodyEventType
    occurred_at: dt.datetime
    actor_id: uuid.UUID
    from_facility_id: uuid.UUID | None
    to_facility_id: uuid.UUID | None
    notes: str | None


class PassportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    passport_code: str
    material_category_id: uuid.UUID
    status: PassportStatus
    description: str | None
    weight_kg: decimal.Decimal
    origin_collection_task_id: uuid.UUID | None
    recovery_record_id: uuid.UUID | None
    current_facility_id: uuid.UUID | None
    created_by_id: uuid.UUID
    created_at: dt.datetime
    updated_at: dt.datetime


class PassportDetail(PassportOut):
    events: list[EventOut]


class Integrity(BaseModel):
    passport_code: str
    valid: bool
    events: int
    problems: list[str]
    basis: str = (
        "Checks the recorded chain: contiguous sequence numbers, starts with `created`, times "
        "never go backwards, every step is an allowed successor. The database rejects edits "
        "and deletions of custody events. This is not a cryptographic proof or a blockchain."
    )
