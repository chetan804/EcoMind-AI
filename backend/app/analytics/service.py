"""Analytics: role-specific dashboards computed from real underlying data.

Every number is derived from a SQL aggregation over the organization's own
rows — no fabricated metrics, no hardcoded trends. Empty organizations show
empty states, not fake data.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import case, func, select

from app.collection.models import CollectionEvent, CollectionPoint, EventStatus
from app.complaints.models import Complaint, ComplaintStatus
from app.core.db import AsyncSession
from app.fleet.models import Vehicle, VehicleStatus
from app.iot.models import Alert, AlertStatus, Device, DeviceStatus
from app.rewards.models import RewardLedger
from app.routing.models import Route, RouteStatus
from app.waste.models import ReportStatus, WasteReport


async def operations_dashboard(session: AsyncSession, *, organization_id: uuid.UUID, days: int = 30) -> dict:
    since = date.today() - timedelta(days=days - 1)

    events_q = select(
        func.count().label("total"),
        func.sum(case((CollectionEvent.status == EventStatus.completed, 1), else_=0)).label("completed"),
        func.sum(case((CollectionEvent.status == EventStatus.missed, 1), else_=0)).label("missed"),
        func.sum(case((CollectionEvent.status == EventStatus.skipped, 1), else_=0)).label("skipped"),
        func.coalesce(
            func.sum(case((CollectionEvent.status == EventStatus.completed, CollectionEvent.weight_kg))), 0
        ).label("weight"),
    ).where(
        CollectionEvent.organization_id == organization_id,
        CollectionEvent.scheduled_date >= since,
    )
    e = (await session.execute(events_q)).one()

    completion_rate = (float(e.completed) / float(e.total)) if e.total else None

    # Daily trend for completion + weight
    trend_rows = (
        await session.execute(
            select(
                CollectionEvent.scheduled_date.label("d"),
                func.count().label("total"),
                func.sum(case((CollectionEvent.status == EventStatus.completed, 1), else_=0)).label("done"),
                func.coalesce(func.sum(CollectionEvent.weight_kg), 0).label("weight"),
            )
            .where(
                CollectionEvent.organization_id == organization_id,
                CollectionEvent.scheduled_date >= since,
            )
            .group_by(CollectionEvent.scheduled_date)
            .order_by(CollectionEvent.scheduled_date)
        )
    ).all()

    open_reports = (
        await session.execute(
            select(func.count()).select_from(WasteReport).where(
                WasteReport.organization_id == organization_id,
                WasteReport.status.in_([ReportStatus.submitted, ReportStatus.triaged, ReportStatus.in_progress]),
            )
        )
    ).scalar_one()

    open_complaints = (
        await session.execute(
            select(func.count()).select_from(Complaint).where(
                Complaint.organization_id == organization_id,
                Complaint.status.in_([
                    ComplaintStatus.submitted, ComplaintStatus.triaged,
                    ComplaintStatus.assigned, ComplaintStatus.in_progress,
                ]),
            )
        )
    ).scalar_one()

    open_alerts = (
        await session.execute(
            select(func.count()).select_from(Alert).where(
                Alert.organization_id == organization_id,
                Alert.status == AlertStatus.open,
            )
        )
    ).scalar_one()

    active_routes = (
        await session.execute(
            select(func.count()).select_from(Route).where(
                Route.organization_id == organization_id,
                Route.status == RouteStatus.in_progress,
            )
        )
    ).scalar_one()

    vehicles_active = (
        await session.execute(
            select(func.count()).select_from(Vehicle).where(
                Vehicle.organization_id == organization_id,
                Vehicle.status == VehicleStatus.active,
            )
        )
    ).scalar_one()

    devices_online = (
        await session.execute(
            select(func.count()).select_from(Device).where(
                Device.organization_id == organization_id,
                Device.status == DeviceStatus.active,
            )
        )
    ).scalar_one()
    devices_total = (
        await session.execute(
            select(func.count()).select_from(Device).where(Device.organization_id == organization_id)
        )
    ).scalar_one()

    return {
        "period_days": days,
        "collection": {
            "total_events": int(e.total or 0),
            "completed": int(e.completed or 0),
            "missed": int(e.missed or 0),
            "skipped": int(e.skipped or 0),
            "completion_rate": round(completion_rate, 4) if completion_rate is not None else None,
            "weight_collected_kg": round(float(e.weight or 0), 1),
        },
        "trend": [
            {"date": str(r.d), "total": int(r.total), "completed": int(r.done or 0),
             "weight_kg": round(float(r.weight or 0), 1)}
            for r in trend_rows
        ],
        "work": {"open_reports": open_reports, "open_complaints": open_complaints, "open_alerts": open_alerts},
        "fleet": {"active_vehicles": vehicles_active, "routes_in_progress": active_routes},
        "iot": {"devices_online": devices_online, "devices_total": devices_total},
    }


async def citizen_dashboard(
    session: AsyncSession, *, organization_id: uuid.UUID, user_id: uuid.UUID, days: int = 30
) -> dict:
    since = date.today() - timedelta(days=days - 1)
    from app.sustainability.models import WasteTreatment

    my_reports = (
        await session.execute(
            select(func.count()).select_from(WasteReport).where(
                WasteReport.organization_id == organization_id,
                WasteReport.reporter_user_id == user_id,
            )
        )
    ).scalar_one()
    my_resolved = (
        await session.execute(
            select(func.count()).select_from(WasteReport).where(
                WasteReport.organization_id == organization_id,
                WasteReport.reporter_user_id == user_id,
                WasteReport.status.in_([ReportStatus.resolved, ReportStatus.closed]),
            )
        )
    ).scalar_one()

    points = (
        await session.execute(
            select(func.count()).select_from(CollectionPoint).where(
                CollectionPoint.organization_id == organization_id
            )
        )
    ).scalar_one()

    treatment_rows = (
        await session.execute(
            select(WasteTreatment.destination, func.sum(WasteTreatment.weight_kg)).where(
                WasteTreatment.organization_id == organization_id,
            ).group_by(WasteTreatment.destination)
        )
    ).all()
    by_dest = {d: float(w or 0) for d, w in treatment_rows}

    community_reports = (
        await session.execute(
            select(func.count()).select_from(WasteReport).where(
                WasteReport.organization_id == organization_id,
                WasteReport.created_at >= since,
            )
        )
    ).scalar_one()

    points_total_weight = sum(by_dest.values())

    # Upcoming collections for this zone (nearest days with scheduled events)
    upcoming = (
        await session.execute(
            select(CollectionEvent.scheduled_date, func.count())
            .where(
                CollectionEvent.organization_id == organization_id,
                CollectionEvent.scheduled_date >= date.today(),
                CollectionEvent.status == EventStatus.scheduled,
            )
            .group_by(CollectionEvent.scheduled_date)
            .order_by(CollectionEvent.scheduled_date)
            .limit(7)
        )
    ).all()

    return {
        "my_reports": my_reports,
        "my_resolved": my_resolved,
        "community_reports_30d": community_reports,
        "collection_points": points,
        "community_weight_kg": round(points_total_weight, 1),
        "by_destination": {k: round(v, 1) for k, v in by_dest.items()},
        "upcoming_collection_days": [{"date": str(d), "scheduled": c} for d, c in upcoming],
    }


async def executive_dashboard(session: AsyncSession, *, organization_id: uuid.UUID, days: int = 90) -> dict:
    ops = await operations_dashboard(session, organization_id=organization_id, days=days)

    resolved_complaints = (
        await session.execute(
            select(func.count()).select_from(Complaint).where(
                Complaint.organization_id == organization_id,
                Complaint.status.in_([ComplaintStatus.resolved, ComplaintStatus.closed]),
            )
        )
    ).scalar_one()
    total_complaints = (
        await session.execute(
            select(func.count()).select_from(Complaint).where(
                Complaint.organization_id == organization_id
            )
        )
    ).scalar_one()

    avg_resolution_hours = None
    if total_complaints:
        row = (
            await session.execute(
                select(func.avg(Complaint.resolved_at - Complaint.created_at)).where(
                    Complaint.organization_id == organization_id,
                    Complaint.resolved_at.is_not(None),
                )
            )
        ).scalar_one()
        if row is not None:
            avg_resolution_hours = round(row.total_seconds() / 3600, 1)

    route_rows = (
        await session.execute(
            select(
                func.count().label("routes"),
                func.coalesce(func.avg(Route.total_distance_km), 0).label("avg_km"),
                func.coalesce(func.sum(Route.total_distance_km), 0).label("total_km"),
                func.coalesce(func.avg(Route.total_duration_min), 0).label("avg_min"),
            ).where(
                Route.organization_id == organization_id,
                Route.status == RouteStatus.completed,
            )
        )
    ).one()

    rewards = (
        await session.execute(
            select(func.count(func.distinct(RewardLedger.user_id))).where(
                RewardLedger.organization_id == organization_id
            )
        )
    ).scalar_one()

    return {
        **ops,
        "complaints": {
            "total": total_complaints,
            "resolved": resolved_complaints,
            "resolution_rate": round(resolved_complaints / total_complaints, 4) if total_complaints else None,
            "avg_resolution_hours": avg_resolution_hours,
        },
        "routes": {
            "completed": int(route_rows.routes or 0),
            "avg_distance_km": round(float(route_rows.avg_km or 0), 1),
            "total_distance_km": round(float(route_rows.total_km or 0), 1),
            "avg_duration_min": round(float(route_rows.avg_min or 0), 1),
        },
        "participation": {"citizens_with_activity": rewards},
    }
