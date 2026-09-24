"""Organization / unit / zone / membership schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    org_type: str = "municipality"
    timezone: str = "UTC"
    city: str | None = None
    country: str | None = None
    contact_email: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    org_type: str | None = None
    timezone: str | None = None
    city: str | None = None
    country: str | None = None
    contact_email: str | None = None
    allow_citizen_signup: bool | None = None
    allow_anonymous_reports: bool | None = None
    branding: dict | None = None
    settings: dict | None = None


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name: str
    org_type: str
    status: str
    timezone: str
    locale: str
    city: str | None
    country: str | None
    contact_email: str | None
    is_demo: bool
    allow_citizen_signup: bool
    allow_anonymous_reports: bool
    branding: dict
    settings: dict
    created_at: datetime


class UnitCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=32)
    description: str | None = None


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: str
    description: str | None
    created_at: datetime


class ZoneCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=32)
    unit_id: uuid.UUID | None = None
    color_hex: str = "#10b981"
    boundary: dict[str, Any]  # GeoJSON Polygon

    @field_validator("boundary")
    @classmethod
    def _validate_boundary(cls, v):
        from app.core.gis import parse_polygon_geojson

        parse_polygon_geojson(v)
        return v


class ZoneOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    unit_id: uuid.UUID | None
    color_hex: str
    boundary: dict
    centroid_lat: float
    centroid_lng: float
    created_at: datetime


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    email: str
    full_name: str
    role_code: str
    is_active: bool
    joined_at: datetime


class MemberUpdate(BaseModel):
    role_code: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class InviteCreate(BaseModel):
    email: str
    role_code: str = "citizen"


class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    role_code: str
    expires_at: datetime
    invite_token: str  # surfaced once, only to the inviting admin


class InviteAccept(BaseModel):
    token: str
