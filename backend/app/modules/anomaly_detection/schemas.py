from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.common.enums import QuantityUnit
from app.modules.anomaly_detection.constants import AlertStatus, AnomalySeverity

Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
DataKind = Literal["platform", "public_reference"]
SortField = Literal["detected_at", "window_start", "severity", "status"]


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: str = Field(min_length=3, max_length=80)
    lookback_weeks: int = Field(default=26, ge=1, le=520)


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Note | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    metric: str
    data_kind: DataKind = "platform"
    unit: QuantityUnit
    severity: AnomalySeverity
    status: AlertStatus
    window_start: dt.datetime
    window_end: dt.datetime
    observed_value: decimal.Decimal
    expected_value: decimal.Decimal
    threshold_value: decimal.Decimal | None
    detector_name: str
    detector_version: str
    explanation: str
    detected_at: dt.datetime
    acknowledged_by_id: uuid.UUID | None
    acknowledged_at: dt.datetime | None
    resolved_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime


class ScanOut(BaseModel):
    series: str
    data_kind: DataKind
    detector: str
    weeks_scanned: int
    weeks_considered: int
    flagged: int
    created: int
    already_recorded: int
    alerts: list[AlertOut]
    caveat: str
