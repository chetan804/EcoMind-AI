"""Request and response bodies of the waste-reports API."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.common.enums import SortOrder
from app.modules.waste_reports.constants import MAX_ATTACHMENTS_PER_REPORT, WasteReportStatus

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]

SortField = Literal["reported_at", "title", "status", "estimated_weight_kg"]
ReviewTarget = Literal["under_review", "verified", "rejected", "closed"]


class WasteReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: LongText | None = None
    address_text: Address | None = None
    latitude: decimal.Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: decimal.Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    estimated_weight_kg: decimal.Decimal | None = Field(
        default=None, ge=0, le=100_000, decimal_places=3
    )
    media_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_ATTACHMENTS_PER_REPORT)

    @model_validator(mode="after")
    def _point_is_complete(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if len(set(self.media_ids)) != len(self.media_ids):
            raise ValueError("media_ids must not contain duplicates")
        return self


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReviewTarget
    reason: Reason | None = None

    @model_validator(mode="after")
    def _rejection_needs_reason(self) -> Self:
        if self.status == "rejected" and self.reason is None:
            raise ValueError("A reason is required when rejecting a report")
        return self


class MediaOut(BaseModel):
    id: uuid.UUID
    content_type: str
    size_bytes: int
    width_px: int | None
    height_px: int | None
    created_at: dt.datetime
    # Relative: the client resolves it against its configured API base URL.
    content_path: str


class WasteReportOut(BaseModel):
    id: uuid.UUID
    reporter_id: uuid.UUID
    status: WasteReportStatus
    title: str
    description: str | None
    address_text: str | None
    latitude: decimal.Decimal | None
    longitude: decimal.Decimal | None
    estimated_weight_kg: decimal.Decimal | None
    reported_at: dt.datetime
    updated_at: dt.datetime
    media: list[MediaOut]


class WasteReportQuery(BaseModel):
    """Validated list filters (built from query parameters by the router)."""

    status: WasteReportStatus | None = None
    q: str | None = None
    mine: bool = False
    reported_from: dt.datetime | None = None
    reported_to: dt.datetime | None = None
    # Area filter: a latitude/longitude box (all four values or none; no antimeridian crossing).
    min_latitude: decimal.Decimal | None = None
    max_latitude: decimal.Decimal | None = None
    min_longitude: decimal.Decimal | None = None
    max_longitude: decimal.Decimal | None = None
    sort_by: SortField = "reported_at"
    order: SortOrder = SortOrder.DESC
