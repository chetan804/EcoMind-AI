from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CollectionCreate(BaseModel):
    report_id: int
    collector_id: int | None = None
    scheduled_at: datetime | None = None


class CollectionStatusUpdate(BaseModel):
    status: Literal[
        "assigned",
        "accepted",
        "in_progress",
        "arrived",
        "collected",
        "verified",
        "cancelled",
    ]


class CollectionResponse(BaseModel):
    id: int
    report_id: int
    collector_id: int | None
    status: str
    scheduled_at: datetime | None
    collected_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True