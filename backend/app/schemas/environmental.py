from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentalSourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    source_type: str = Field(default="manual", min_length=2, max_length=30)
    location: str = Field(min_length=2, max_length=255)


class EnvironmentalReadingCreate(BaseModel):
    metric: str = Field(min_length=2, max_length=50)
    value: float
    unit: str = Field(min_length=1, max_length=20)


class EnvironmentalReadingResponse(EnvironmentalReadingCreate):
    id: int
    source_id: int
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EnvironmentalSourceResponse(EnvironmentalSourceCreate):
    id: int
    is_active: bool
    created_at: datetime
    readings: list[EnvironmentalReadingResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SmartBinCreate(BaseModel):
    bin_code: str = Field(min_length=2, max_length=80)
    location: str = Field(min_length=2, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class SmartBinUpdate(BaseModel):
    fill_level: float | None = Field(default=None, ge=0, le=100)
    battery_level: float | None = Field(default=None, ge=0, le=100)
    status: str | None = Field(default=None, min_length=2, max_length=30)


class SmartBinResponse(SmartBinCreate):
    id: int
    fill_level: float | None
    battery_level: float | None
    last_seen_at: datetime | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
