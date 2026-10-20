from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.modules.fleet.constants import VehicleStatus, VehicleType
from app.modules.tracking.constants import LocationQuality, LocationSource, TrackingStatus

Latitude = Annotated[decimal.Decimal, Field(ge=-90, le=90, decimal_places=6, max_digits=9)]
Longitude = Annotated[decimal.Decimal, Field(ge=-180, le=180, decimal_places=6, max_digits=9)]
Accuracy = Annotated[decimal.Decimal, Field(ge=0, le=100000, decimal_places=2, max_digits=9)]
Speed = Annotated[decimal.Decimal, Field(ge=0, le=300, decimal_places=2, max_digits=6)]
Heading = Annotated[decimal.Decimal, Field(ge=0, lt=360, decimal_places=2, max_digits=5)]
Sequence = Annotated[int, Field(ge=0, le=2**62)]


class _LocationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: Latitude
    longitude: Longitude
    accuracy_m: Accuracy | None = None
    speed_kph: Speed | None = Field(default=None, description="Only if the device measured it")
    heading_deg: Heading | None = Field(default=None, description="Only if the device measured it")
    sequence: Sequence | None = Field(
        default=None, description="Per vehicle and source, strictly increasing; makes retries safe"
    )
    collection_task_id: uuid.UUID | None = None
    route_plan_id: uuid.UUID | None = None


class LocationReport(_LocationBody):
    """A position posted by a tracker, the collector's phone, or an import."""

    recorded_at: AwareDatetime = Field(description="When the position was measured (any offset)")
    source: Literal["gps_device", "mobile_client", "imported"]


class SimulatedLocation(_LocationBody):
    """A position posted by the simulator. ``recorded_at`` defaults to the server clock."""

    recorded_at: AwareDatetime | None = None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_id: uuid.UUID
    latitude: decimal.Decimal
    longitude: decimal.Decimal
    recorded_at: dt.datetime
    received_at: dt.datetime
    source: LocationSource
    quality: LocationQuality
    accuracy_m: decimal.Decimal | None
    speed_kph: decimal.Decimal | None
    heading_deg: decimal.Decimal | None
    sequence: int | None
    collection_task_id: uuid.UUID | None
    route_plan_id: uuid.UUID | None


class IngestResult(BaseModel):
    duplicate: bool = Field(description="True when this event was already stored (retry)")
    event: LocationOut


class PositionOut(BaseModel):
    latitude: decimal.Decimal
    longitude: decimal.Decimal
    recorded_at: dt.datetime
    received_at: dt.datetime
    source: LocationSource
    accuracy_m: decimal.Decimal | None
    speed_kph: decimal.Decimal | None
    heading_deg: decimal.Decimal | None
    age_seconds: int = Field(description="Server clock minus recorded_at, never negative")
    collection_task_id: uuid.UUID | None
    route_plan_id: uuid.UUID | None


class VehiclePosition(BaseModel):
    """One row per vehicle and data group. A vehicle with both real and simulated data has two."""

    vehicle_id: uuid.UUID
    registration_number: str
    vehicle_type: VehicleType
    vehicle_status: VehicleStatus
    simulated: bool
    status: TrackingStatus
    position: PositionOut | None


class LatestPositions(BaseModel):
    generated_at: dt.datetime
    live_within_seconds: int
    stale_after_seconds: int
    items: list[VehiclePosition]


class TrackingConfig(BaseModel):
    live_within_seconds: int
    stale_after_seconds: int
    retention_days: int
    simulator_enabled: bool
    max_events_per_minute: int
    road_routing_configured: bool


class StopProgress(BaseModel):
    sequence: int
    kind: Literal["task", "facility"]
    label: str
    latitude: decimal.Decimal
    longitude: decimal.Decimal
    task_id: uuid.UUID | None
    task_status: str | None = Field(description="Authoritative state from the collection module")
    completed: bool


class PathPoint(BaseModel):
    latitude: decimal.Decimal
    longitude: decimal.Decimal
    recorded_at: dt.datetime
    source: LocationSource


class RouteTracking(BaseModel):
    """Plan stops with their real state, the vehicle's position and the recorded path."""

    route_plan_id: uuid.UUID
    plan_status: str
    vehicle_id: uuid.UUID | None
    stops: list[StopProgress]
    completed_task_stops: int
    total_task_stops: int
    vehicle: VehiclePosition | None
    path: list[PathPoint]
    path_simulated: bool
    path_truncated: bool
    basis: str = (
        "Stop states come from the collection tasks. The path is the vehicle's recorded "
        "positions, not a navigation route; it is empty when no events were received."
    )


class CollectionTracking(BaseModel):
    task_id: uuid.UUID
    title: str
    status: str
    latitude: decimal.Decimal | None
    longitude: decimal.Decimal | None
    destination_facility_id: uuid.UUID | None
    vehicle_id: uuid.UUID | None
    vehicle: VehiclePosition | None
    path: list[PathPoint]
    path_truncated: bool
    basis: str = (
        "The path contains only positions linked to this task. Positions that were not linked "
        "are not guessed."
    )
