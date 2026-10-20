"""Request and response bodies of the fleet API."""

from __future__ import annotations

import datetime as dt
import decimal
import re
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.fleet.constants import VehicleStatus, VehicleType

REGISTRATION_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9 -]{2,30}[A-Z0-9]$")
CapacityKg = Annotated[decimal.Decimal, Field(gt=0, le=1_000_000, decimal_places=3)]

SortField = Literal["registration_number", "capacity_kg", "status", "created_at"]


def _registration(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip().upper())
    if not REGISTRATION_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "registration_number must be 4-32 characters: letters, digits, spaces or '-'"
        )
    return cleaned


class VehicleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registration_number: str
    vehicle_type: VehicleType
    capacity_kg: CapacityKg
    status: VehicleStatus = VehicleStatus.AVAILABLE
    home_facility_id: uuid.UUID | None = None

    _registration = field_validator("registration_number")(lambda cls, v: _registration(v))


class VehicleUpdate(BaseModel):
    """Partial update; the registration number is immutable (it is the vehicle's identity)."""

    model_config = ConfigDict(extra="forbid")

    vehicle_type: VehicleType | None = None
    capacity_kg: CapacityKg | None = None
    status: VehicleStatus | None = None
    home_facility_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _required_fields_cannot_be_cleared(self) -> VehicleUpdate:
        for field in ("vehicle_type", "capacity_kg", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    registration_number: str
    vehicle_type: VehicleType
    status: VehicleStatus
    capacity_kg: decimal.Decimal
    home_facility_id: uuid.UUID | None
    # Number of non-finished collection tasks currently assigned to this vehicle.
    active_task_count: int = 0
    created_at: dt.datetime
    updated_at: dt.datetime
