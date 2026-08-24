from datetime import datetime

from pydantic import BaseModel


class WasteReportCreate(BaseModel):
    waste_type: str
    description: str
    location: str


class WasteReportResponse(BaseModel):
    id: int
    user_id: int
    waste_type: str
    description: str
    location: str
    status: str
    ai_waste_type: str | None = None
    ai_confidence: float | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class WasteClassificationResponse(BaseModel):
    report_id: int
    waste_type: str
    confidence: float