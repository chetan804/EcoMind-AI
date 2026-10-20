"""Request and response bodies of the community-incident API."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.community_incidents.constants import IncidentStatus, IncidentType

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=5000)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
Latitude = Annotated[decimal.Decimal, Field(ge=-90, le=90, decimal_places=6)]
Longitude = Annotated[decimal.Decimal, Field(ge=-180, le=180, decimal_places=6)]
SortField = Literal["created_at", "updated_at", "status", "incident_type"]


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_type: IncidentType
    title: Title
    description: Text | None = None
    address_text: Address | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    photo_media_asset_id: uuid.UUID | None = Field(
        default=None, description="A file the reporter uploaded via POST /waste-reports/media"
    )

    @model_validator(mode="after")
    def _location(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.latitude is None and not self.address_text:
            raise ValueError("a location is required: coordinates or an address")
        return self


class AssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_id: uuid.UUID


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["acknowledged", "in_progress", "resolved", "dismissed"]
    notes: Text | None = None

    @model_validator(mode="after")
    def _closing_needs_notes(self) -> Self:
        if self.status in ("resolved", "dismissed") and not self.notes:
            raise ValueError("notes are required when resolving or dismissing an incident")
        return self


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reporter_id: uuid.UUID
    assigned_to_id: uuid.UUID | None
    incident_type: IncidentType
    status: IncidentStatus
    title: str
    description: str | None
    address_text: str | None
    latitude: decimal.Decimal | None
    longitude: decimal.Decimal | None
    photo_media_asset_id: uuid.UUID | None
    photo_content_path: str | None = None
    resolved_at: dt.datetime | None
    resolution_notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class Count(BaseModel):
    key: str
    count: int


class IncidentSummary(BaseModel):
    total: int
    open_incidents: int = Field(description="Not yet resolved or dismissed")
    unassigned_open: int
    by_status: list[Count]
    by_type: list[Count]
