from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RouteStopResponse(BaseModel):
    id: int
    collection_id: int
    stop_order: int
    distance_from_previous_km: float

    model_config = ConfigDict(from_attributes=True)


class RouteResponse(BaseModel):
    id: int
    collector_id: int
    status: str
    estimated_distance_km: float
    estimated_duration_minutes: float
    created_at: datetime
    stops: list[RouteStopResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
