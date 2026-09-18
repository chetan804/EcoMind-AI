from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


WasteType = Literal[
    "plastic",
    "paper",
    "glass",
    "metal",
    "organic",
    "e-waste",
    "other",
]


class WasteReportCreate(BaseModel):
    waste_type: WasteType
    description: str = Field(min_length=3, max_length=5000)
    location: str = Field(min_length=2, max_length=255)
    image_path: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class WasteReportResponse(BaseModel):
    id: int
    user_id: int
    waste_type: WasteType
    description: str
    location: str
    image_path: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: str
    ai_waste_type: str | None = None
    ai_confidence: float | None = None
    ai_model_name: str | None = None
    ai_model_version: str | None = None
    ai_provider: str | None = None
    ai_inference_ms: float | None = None
    ai_created_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WasteClassificationResponse(BaseModel):
    report_id: int
    waste_type: str
    confidence: float
    model_name: str | None = None
    model_version: str | None = None
    provider: str | None = None
    inference_time_ms: float | None = None