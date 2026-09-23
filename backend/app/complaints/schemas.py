"""Complaint schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.gis import MAX_LAT, MAX_LNG, MIN_LAT, MIN_LNG


class ComplaintCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    category: str = "other"
    priority: str | None = None  # optional operator override; AI suggests otherwise
    waste_report_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    latitude: float | None = Field(default=None, ge=MIN_LAT, le=MAX_LAT)
    longitude: float | None = Field(default=None, ge=MIN_LNG, le=MAX_LNG)


class ComplaintUpdateIn(BaseModel):
    new_status: str | None = None
    priority: str | None = None
    category: str | None = None
    assignee: uuid.UUID | None = None
    resolution_summary: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    subject: str
    description: str | None
    category: str
    status: str
    priority: str
    waste_report_id: uuid.UUID | None
    reporter_user_id: uuid.UUID | None
    reporter_name: str | None = None
    complainant_contact: str | None
    assignee_name: str | None = None
    assigned_to: uuid.UUID | None
    zone_id: uuid.UUID | None
    latitude: float | None
    longitude: float | None
    due_at: datetime | None
    first_response_at: datetime | None
    resolved_at: datetime | None
    resolution_summary: str | None
    satisfaction_rating: int | None
    created_at: datetime
    updated_at: datetime | None
