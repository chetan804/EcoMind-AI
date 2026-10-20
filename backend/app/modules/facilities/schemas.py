"""Request and response bodies of the facilities API."""

from __future__ import annotations

import datetime as dt
import decimal
import re
import uuid
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.facilities.constants import FacilityStatus, FacilityType

CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,31}$")
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Place = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Capacity = Annotated[decimal.Decimal, Field(gt=0, le=1_000_000_000, decimal_places=3)]
Latitude = Annotated[decimal.Decimal, Field(ge=-90, le=90, decimal_places=6)]
Longitude = Annotated[decimal.Decimal, Field(ge=-180, le=180, decimal_places=6)]

SortField = Literal["name", "code", "city", "daily_capacity_kg", "created_at"]


def _country(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        raise ValueError("country_code must be a two-letter ISO 3166-1 alpha-2 code")
    return code


class FacilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: Name
    facility_type: FacilityType
    status: FacilityStatus = FacilityStatus.ACTIVE
    address_line: Line | None = None
    city: Place | None = None
    region: Place | None = None
    country_code: str | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    daily_capacity_kg: Capacity | None = None
    contact_email: EmailStr | None = None

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        code = value.strip().upper()
        if not CODE_PATTERN.fullmatch(code):
            raise ValueError(
                "code must be 2-32 characters: letters, digits, '-' or '_', starting with a "
                "letter or digit"
            )
        return code

    _country_code = field_validator("country_code")(lambda cls, v: _country(v))

    @model_validator(mode="after")
    def _point_is_complete(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class FacilityUpdate(BaseModel):
    """Partial update: only the fields that are sent change. ``code`` is immutable."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    facility_type: FacilityType | None = None
    status: FacilityStatus | None = None
    address_line: Line | None = None
    city: Place | None = None
    region: Place | None = None
    country_code: str | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    daily_capacity_kg: Capacity | None = None
    contact_email: EmailStr | None = None

    _country_code = field_validator("country_code")(lambda cls, v: _country(v))

    @model_validator(mode="after")
    def _required_fields_cannot_be_cleared(self) -> Self:
        for field in ("name", "facility_type", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class FacilityOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    facility_type: FacilityType
    status: FacilityStatus
    address_line: str | None
    city: str | None
    region: str | None
    country_code: str | None
    latitude: decimal.Decimal | None
    longitude: decimal.Decimal | None
    daily_capacity_kg: decimal.Decimal | None
    # Only returned to callers who can manage facilities (it may be a personal address).
    contact_email: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
