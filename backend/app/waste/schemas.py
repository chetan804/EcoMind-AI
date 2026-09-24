"""Waste report schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.errors import ValidationApiError
from app.core.gis import MAX_LAT, MAX_LNG, MIN_LAT, MIN_LNG


class ReportCreate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    category_guess: str | None = Field(default=None, max_length=48)
    latitude: float
    longitude: float
    location_accuracy_m: float | None = Field(default=None, ge=0, le=10000)
    address: str | None = Field(default=None, max_length=320)
    is_anonymous: bool = False
    contact: str | None = Field(default=None, max_length=320)
    photo_media_id: uuid.UUID | None = None

    @field_validator("latitude")
    @classmethod
    def _lat(cls, v: float) -> float:
        if not (MIN_LAT <= v <= MAX_LAT):
            raise ValidationApiError("Latitude out of range.")
        return v

    @field_validator("longitude")
    @classmethod
    def _lng(cls, v: float) -> float:
        if not (MIN_LNG <= v <= MAX_LNG):
            raise ValidationApiError("Longitude out of range.")
        return v


class ReportStatusUpdate(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=1000)
    severity: str | None = None
    confirmed_category_id: uuid.UUID | None = None
    resolution_notes: str | None = None


class ReportAssign(BaseModel):
    user_id: uuid.UUID


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    description: str | None
    latitude: float
    longitude: float
    address: str | None
    status: str
    severity: str
    source: str
    category_guess: str | None
    confirmed_category_id: uuid.UUID | None
    photo_media_id: uuid.UUID | None
    is_anonymous: bool
    reporter_user_id: uuid.UUID | None
    reporter_name: str | None = None
    assigned_to: uuid.UUID | None
    assigned_to_name: str | None = None
    zone_id: uuid.UUID | None
    zone_name: str | None = None
    ai_inference_id: uuid.UUID | None
    ai_category: str | None = None
    ai_confidence: float | None = None
    ai_is_simulated: bool | None = None
    resolution_notes: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class ReportEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    note: str | None
    actor_user_id: uuid.UUID | None
    created_at: datetime
