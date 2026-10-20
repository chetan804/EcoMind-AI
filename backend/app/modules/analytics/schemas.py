"""Response bodies of the analytics API. Every figure is computed from stored data on request."""

from __future__ import annotations

import datetime as dt
import decimal

from pydantic import BaseModel, Field

BASIS = (
    "Computed live from the platform database when requested; nothing is cached or estimated. "
    "Weights are collector-recorded kilograms. No carbon, cost or environmental-benefit "
    "coefficients are applied because none are sourced."
)


class Count(BaseModel):
    key: str
    count: int


class ReportStats(BaseModel):
    total: int
    in_window: int
    by_status: list[Count]


class CollectionStats(BaseModel):
    tasks_total: int
    open_tasks: int = Field(description="pending, assigned or in progress")
    overdue_tasks: int = Field(description="Open tasks whose due time has passed")
    completed_in_window: int
    collected_weight_kg_in_window: decimal.Decimal
    collected_weight_kg_total: decimal.Decimal
    by_status: list[Count]


class FleetStats(BaseModel):
    vehicles_total: int
    by_status: list[Count]
    capacity_kg_available: decimal.Decimal = Field(
        description="Summed capacity of vehicles that are available or in service"
    )


class FacilityStats(BaseModel):
    total: int
    active: int


class IncidentStats(BaseModel):
    total: int
    open_incidents: int
    unassigned_open: int


class RecoveryStats(BaseModel):
    verified_records: int
    pending_records: int
    input_weight_kg: decimal.Decimal
    recovered_weight_kg: decimal.Decimal
    recovery_rate: decimal.Decimal | None


class RewardStats(BaseModel):
    entries: int
    users: int
    net_points: int
    impact_weight_kg: decimal.Decimal


class AnomalyStats(BaseModel):
    open_alerts: int = Field(description="Open suspected anomalies (not confirmed incidents)")
    critical_open: int


class PassportStats(BaseModel):
    total: int
    by_status: list[Count]


class Overview(BaseModel):
    generated_at: dt.datetime
    window_days: int
    window_start: dt.datetime
    reports: ReportStats
    collection: CollectionStats
    fleet: FleetStats
    facilities: FacilityStats
    incidents: IncidentStats
    recovery: RecoveryStats
    rewards: RewardStats
    anomalies: AnomalyStats
    passports: PassportStats
    basis: str = BASIS


class WeekPoint(BaseModel):
    week_start: dt.date
    collected_weight_kg: decimal.Decimal
    tasks_completed: int
    reports_submitted: int


class WeeklyTrend(BaseModel):
    weeks: int
    points: list[WeekPoint]
    basis: str = (
        "Calendar weeks starting Monday (UTC). Weeks without activity are real zeros, shown "
        "so gaps are visible; collected weight is summed from `collected` field events."
    )
