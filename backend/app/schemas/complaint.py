from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ComplaintStatus = Literal[
    "submitted",
    "under_review",
    "assigned",
    "in_progress",
    "resolved",
    "rejected",
]


class ComplaintCreate(BaseModel):
    description: str = Field(min_length=3, max_length=5000)
    location: str = Field(min_length=2, max_length=255)
    report_id: int | None = None


class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    resolution: str | None = Field(default=None, max_length=5000)
    assigned_to: int | None = None
    note: str | None = Field(default=None, max_length=2000)


class ComplaintHistoryResponse(BaseModel):
    id: int
    changed_by: int
    old_status: str | None
    new_status: str
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplaintResponse(BaseModel):
    id: int
    user_id: int
    report_id: int | None
    assigned_to: int | None
    description: str
    location: str
    status: str
    resolution: str | None
    created_at: datetime
    updated_at: datetime
    history: list[ComplaintHistoryResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
