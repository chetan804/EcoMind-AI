from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.route_planning.constants import RoutePlanStatus

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
SortField = Literal["planned_date", "created_at", "total_distance_km", "status"]
MAX_STOPS = 40

BASIS = (
    "Stop order minimises the total great-circle (straight-line) distance. Road distances, "
    "traffic, time windows and vehicle capacity beyond the checks listed in `warnings` are not "
    "modelled, and no travel time is estimated."
)


class PlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    planned_date: dt.date
    start_facility_id: uuid.UUID = Field(description="Depot the vehicle leaves from and returns to")
    end_facility_id: uuid.UUID | None = Field(
        default=None, description="Facility visited last (e.g. disposal) before returning"
    )
    task_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_STOPS)
    vehicle_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None


class StopOut(BaseModel):
    sequence: int
    kind: Literal["task", "facility"]
    collection_task_id: uuid.UUID | None
    facility_id: uuid.UUID | None
    label: str
    latitude: decimal.Decimal
    longitude: decimal.Decimal
    leg_distance_km: decimal.Decimal = Field(
        description="Straight-line distance from the previous point"
    )


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    planned_date: dt.date
    status: RoutePlanStatus
    vehicle_id: uuid.UUID | None
    driver_id: uuid.UUID | None
    start_facility_id: uuid.UUID | None
    end_facility_id: uuid.UUID | None
    created_by_id: uuid.UUID
    total_distance_km: decimal.Decimal | None
    optimizer: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class PlanDetail(PlanOut):
    start_label: str | None = None
    start_latitude: decimal.Decimal | None = None
    start_longitude: decimal.Decimal | None = None
    return_leg_distance_km: decimal.Decimal | None = None
    stops: list[StopOut]
    warnings: list[str] = []
    basis: str = BASIS


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]
        | None
    ) = None


class RoadRouteOut(BaseModel):
    """A road route from a routing provider, or an explicit statement that none is available.

    When ``available`` is false the client must draw straight lines between the stops and label
    them as such; it must not present them as roads. ``distance_m`` / ``duration_s`` exist only
    for real provider routes and are free-flow estimates (no live traffic).
    """

    plan_id: uuid.UUID
    available: bool
    provider: str | None = None
    reason: str | None = None
    detail: str | None = None
    encoded_polylines: list[str] = []
    distance_m: int | None = None
    duration_s: int | None = None
    traffic_aware: bool = False
    request_count: int = 0
    basis: str = (
        "Road geometry, distance and duration come from the routing provider for the stop order "
        "shown, driving mode, without live traffic. The stop order itself was chosen by the "
        "platform's straight-line optimiser and is not re-optimised for road distance."
    )
