"""Request and response bodies of the collection API."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.collection.constants import CollectionEventType, CollectionTaskStatus, TaskPriority

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
WeightKg = Annotated[decimal.Decimal, Field(gt=0, le=100_000, decimal_places=3)]
Latitude = Annotated[decimal.Decimal, Field(ge=-90, le=90, decimal_places=6)]
Longitude = Annotated[decimal.Decimal, Field(ge=-180, le=180, decimal_places=6)]
SortField = Literal["created_at", "due_at", "priority", "status"]


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("timestamps must include a UTC offset (for example 2026-10-20T09:00:00Z)")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(_Strict):
    """Create a task, usually from a verified waste report (location is then copied from it)."""

    waste_report_id: uuid.UUID | None = None
    title: Title | None = None
    priority: TaskPriority = TaskPriority.NORMAL
    due_at: dt.datetime | None = None
    address_text: Address | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    destination_facility_id: uuid.UUID | None = None
    notes: Note | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _aware(self.due_at)
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.waste_report_id is None and self.title is None:
            raise ValueError("title is required when the task is not created from a report")
        return self


class AssignRequest(_Strict):
    assignee_id: uuid.UUID
    vehicle_id: uuid.UUID | None = None
    note: Note | None = None


class EventCreate(_Strict):
    event_type: CollectionEventType
    occurred_at: dt.datetime | None = None
    facility_id: uuid.UUID | None = None
    notes: Note | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _aware(self.occurred_at)
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class CompleteRequest(_Strict):
    """Outcome of a successful collection. The weight is what the collector actually weighed."""

    collected_weight_kg: WeightKg
    destination_facility_id: uuid.UUID | None = None
    notes: Note | None = None


class ReasonRequest(_Strict):
    reason: Reason


class RescheduleRequest(_Strict):
    due_at: dt.datetime
    note: Note | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        _aware(self.due_at)
        return self


class AssignmentOut(BaseModel):
    id: uuid.UUID
    assignee_id: uuid.UUID
    assignee_name: str
    vehicle_id: uuid.UUID | None
    vehicle_registration: str | None
    assigned_at: dt.datetime
    unassigned_at: dt.datetime | None


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: CollectionTaskStatus | None
    to_status: CollectionTaskStatus
    changed_by_id: uuid.UUID
    note: str | None
    created_at: dt.datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: CollectionEventType
    occurred_at: dt.datetime
    recorded_by_id: uuid.UUID
    facility_id: uuid.UUID | None
    collected_weight_kg: decimal.Decimal | None
    notes: str | None
    latitude: decimal.Decimal | None
    longitude: decimal.Decimal | None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    waste_report_id: uuid.UUID | None
    destination_facility_id: uuid.UUID | None
    title: str
    status: CollectionTaskStatus
    priority: TaskPriority
    address_text: str | None
    latitude: decimal.Decimal | None
    longitude: decimal.Decimal | None
    due_at: dt.datetime | None
    notes: str | None
    created_by_id: uuid.UUID
    assignment: AssignmentOut | None = None
    # Weight recorded by the collector on completion; null until then.
    collected_weight_kg: decimal.Decimal | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class TaskDetail(TaskOut):
    history: list[HistoryOut]
    events: list[EventOut]
