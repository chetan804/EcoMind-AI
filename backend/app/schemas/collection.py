from datetime import datetime

from pydantic import BaseModel


class CollectionCreate(BaseModel):
    report_id: int
    collector_id: int | None = None
    scheduled_at: datetime | None = None


class CollectionStatusUpdate(BaseModel):
    status: str


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