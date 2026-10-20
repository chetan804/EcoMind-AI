"""Analytics read models. Read-only: queries other modules' tables, never writes."""

from __future__ import annotations

import datetime as dt
import decimal
from typing import Any

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.modules.analytics.schemas import (
    AnomalyStats,
    CollectionStats,
    Count,
    FacilityStats,
    FleetStats,
    IncidentStats,
    Overview,
    PassportStats,
    RecoveryStats,
    ReportStats,
    RewardStats,
    WeeklyTrend,
    WeekPoint,
)
from app.modules.anomaly_detection.constants import AlertStatus, AnomalySeverity
from app.modules.anomaly_detection.models import AnomalyAlert
from app.modules.circular_economy import service as recovery
from app.modules.collection.constants import CollectionEventType, CollectionTaskStatus
from app.modules.collection.models import CollectionEvent, CollectionTask
from app.modules.community_incidents import service as incidents
from app.modules.facilities.constants import FacilityStatus
from app.modules.facilities.models import Facility
from app.modules.fleet.constants import VehicleStatus
from app.modules.fleet.models import FleetVehicle
from app.modules.material_passports.constants import PassportStatus
from app.modules.material_passports.models import MaterialPassport
from app.modules.rewards import service as rewards
from app.modules.waste_reports.constants import WasteReportStatus
from app.modules.waste_reports.models import WasteReport

OPEN_TASKS = (
    CollectionTaskStatus.PENDING,
    CollectionTaskStatus.ASSIGNED,
    CollectionTaskStatus.IN_PROGRESS,
)
ZERO = decimal.Decimal(0)


def _counts(db: Session, column: Any, enum_cls: Any) -> list[Count]:
    rows: dict[Any, Any] = dict(db.execute(select(column, func.count()).group_by(column)).all())
    return [Count(key=m.value, count=int(rows.get(m, 0))) for m in enum_cls]


def _weight(db: Session, *conditions: Any) -> decimal.Decimal:
    stmt = select(func.coalesce(func.sum(CollectionEvent.collected_weight_kg), 0)).where(
        CollectionEvent.event_type == CollectionEventType.COLLECTED,
        *conditions,
    )
    return decimal.Decimal(str(db.execute(stmt).scalar_one()))


def overview(db: Session, *, window_days: int, now: dt.datetime | None = None) -> Overview:
    now = now or dt.datetime.now(dt.UTC)
    start = now - dt.timedelta(days=window_days)

    reports_by_status = _counts(db, WasteReport.status, WasteReportStatus)
    reports_in_window = db.execute(
        select(func.count()).where(WasteReport.created_at >= start)
    ).scalar_one()

    tasks_by_status = _counts(db, CollectionTask.status, CollectionTaskStatus)
    overdue = db.execute(
        select(func.count()).where(
            CollectionTask.status.in_(OPEN_TASKS),
            CollectionTask.due_at.is_not(None),
            CollectionTask.due_at < now,
        )
    ).scalar_one()
    completed_in_window = db.execute(
        select(func.count(func.distinct(CollectionEvent.collection_task_id))).where(
            CollectionEvent.event_type == CollectionEventType.COLLECTED,
            CollectionEvent.occurred_at >= start,
        )
    ).scalar_one()
    by_task = {c.key: c.count for c in tasks_by_status}

    vehicles = _counts(db, FleetVehicle.status, VehicleStatus)
    capacity = db.execute(
        select(func.coalesce(func.sum(FleetVehicle.capacity_kg), 0)).where(
            FleetVehicle.status.in_((VehicleStatus.AVAILABLE, VehicleStatus.IN_SERVICE))
        )
    ).scalar_one()

    facilities_total = db.execute(select(func.count()).select_from(Facility)).scalar_one()
    facilities_active = db.execute(
        select(func.count()).where(Facility.status == FacilityStatus.ACTIVE)
    ).scalar_one()

    inc = incidents.summary(db)
    rec = recovery.summary(db, facility_id=None, date_from=None, date_to=None)
    entries, users, issued, removed, impact = rewards.summary(db)

    open_alerts = db.execute(
        select(func.count()).where(AnomalyAlert.status == AlertStatus.OPEN)
    ).scalar_one()
    critical = db.execute(
        select(func.count()).where(
            AnomalyAlert.status == AlertStatus.OPEN,
            AnomalyAlert.severity == AnomalySeverity.CRITICAL,
        )
    ).scalar_one()

    passports = _counts(db, MaterialPassport.status, PassportStatus)

    return Overview(
        generated_at=now,
        window_days=window_days,
        window_start=start,
        reports=ReportStats(
            total=sum(c.count for c in reports_by_status),
            in_window=int(reports_in_window),
            by_status=reports_by_status,
        ),
        collection=CollectionStats(
            tasks_total=sum(by_task.values()),
            open_tasks=sum(by_task[s.value] for s in OPEN_TASKS),
            overdue_tasks=int(overdue),
            completed_in_window=int(completed_in_window),
            collected_weight_kg_in_window=_weight(db, CollectionEvent.occurred_at >= start),
            collected_weight_kg_total=_weight(db),
            by_status=tasks_by_status,
        ),
        fleet=FleetStats(
            vehicles_total=sum(c.count for c in vehicles),
            by_status=vehicles,
            capacity_kg_available=decimal.Decimal(capacity),
        ),
        facilities=FacilityStats(total=int(facilities_total), active=int(facilities_active)),
        incidents=IncidentStats(
            total=inc.total, open_incidents=inc.open_incidents, unassigned_open=inc.unassigned_open
        ),
        recovery=RecoveryStats(
            verified_records=rec.verified_records,
            pending_records=rec.pending_records,
            input_weight_kg=rec.input_weight_kg,
            recovered_weight_kg=rec.recovered_weight_kg,
            recovery_rate=rec.recovery_rate,
        ),
        rewards=RewardStats(
            entries=entries, users=users, net_points=issued - removed, impact_weight_kg=impact
        ),
        anomalies=AnomalyStats(open_alerts=int(open_alerts), critical_open=int(critical)),
        passports=PassportStats(total=sum(c.count for c in passports), by_status=passports),
    )


def _monday(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def weekly_trend(db: Session, *, weeks: int, now: dt.datetime | None = None) -> WeeklyTrend:
    now = now or dt.datetime.now(dt.UTC)
    last = _monday(now.date())
    first = last - dt.timedelta(weeks=weeks - 1)
    start = dt.datetime.combine(first, dt.time.min, tzinfo=dt.UTC)

    def weekly(column: Any, *where: Any, agg: Any) -> dict[dt.date, Any]:
        week = cast(func.date_trunc("week", column), Date)
        stmt = select(week, agg).where(column >= start, *where).group_by(week)
        return {row[0]: row[1] for row in db.execute(stmt).all()}

    weight = weekly(
        CollectionEvent.occurred_at,
        CollectionEvent.event_type == CollectionEventType.COLLECTED,
        agg=func.coalesce(func.sum(CollectionEvent.collected_weight_kg), 0),
    )
    done = weekly(
        CollectionEvent.occurred_at,
        CollectionEvent.event_type == CollectionEventType.COLLECTED,
        agg=func.count(func.distinct(CollectionEvent.collection_task_id)),
    )
    submitted = weekly(WasteReport.created_at, agg=func.count())
    points = []
    for i in range(weeks):
        monday = first + dt.timedelta(weeks=i)
        points.append(
            WeekPoint(
                week_start=monday,
                collected_weight_kg=decimal.Decimal(weight.get(monday, ZERO)),
                tasks_completed=int(done.get(monday, 0)),
                reports_submitted=int(submitted.get(monday, 0)),
            )
        )
    return WeeklyTrend(weeks=weeks, points=points)
