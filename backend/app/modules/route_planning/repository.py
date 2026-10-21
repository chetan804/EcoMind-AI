"""Database access for route plans. No business rules and no commits here."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.enums import SortOrder
from app.common.pagination import PageParams
from app.modules.collection.models import CollectionTask
from app.modules.route_planning.constants import RoutePlanStatus
from app.modules.route_planning.models import RoutePlan, RouteStop
from app.modules.waste_reports.models import WasteReport

ACTIVE = (RoutePlanStatus.DRAFT, RoutePlanStatus.PUBLISHED, RoutePlanStatus.IN_PROGRESS)
_SORT_COLUMNS: dict[str, SQLColumnExpression[Any]] = {
    "planned_date": RoutePlan.planned_date,
    "created_at": RoutePlan.created_at,
    "total_distance_km": RoutePlan.total_distance_km,
    "status": RoutePlan.status,
}


def get(db: Session, plan_id: uuid.UUID, *, for_update: bool = False) -> RoutePlan | None:
    stmt = select(RoutePlan).where(RoutePlan.id == plan_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def add_plan(db: Session, **fields: object) -> RoutePlan:
    plan = RoutePlan(**fields)
    db.add(plan)
    db.flush()
    return plan


def add_stop(db: Session, **fields: object) -> RouteStop:
    stop = RouteStop(**fields)
    db.add(stop)
    db.flush()
    return stop


def stops(db: Session, plan_id: uuid.UUID) -> list[RouteStop]:
    return list(
        db.execute(
            select(RouteStop).where(RouteStop.route_plan_id == plan_id).order_by(RouteStop.sequence)
        ).scalars()
    )


def tasks_with_estimates(
    db: Session, task_ids: list[uuid.UUID]
) -> list[tuple[CollectionTask, decimal.Decimal | None]]:
    stmt = (
        select(CollectionTask, WasteReport.estimated_weight_kg)
        .outerjoin(WasteReport, WasteReport.id == CollectionTask.waste_report_id)
        .where(CollectionTask.id.in_(task_ids))
    )
    return [(task, est) for task, est in db.execute(stmt).all()]


def tasks_in_active_plans(db: Session, task_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Map each task that already sits in an active plan to that plan's name."""
    stmt = (
        select(RouteStop.collection_task_id, RoutePlan.name)
        .join(RoutePlan, RoutePlan.id == RouteStop.route_plan_id)
        .where(RouteStop.collection_task_id.in_(task_ids), RoutePlan.status.in_(ACTIVE))
    )
    return {tid: name for tid, name in db.execute(stmt).all() if tid is not None}


def list_page(
    db: Session,
    params: PageParams,
    *,
    status: RoutePlanStatus | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    sort_by: str,
    order: SortOrder,
) -> tuple[list[RoutePlan], int]:
    stmt = select(RoutePlan)
    if status is not None:
        stmt = stmt.where(RoutePlan.status == status)
    if date_from is not None:
        stmt = stmt.where(RoutePlan.planned_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(RoutePlan.planned_date <= date_to)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _SORT_COLUMNS[sort_by]
    ordering = column.desc() if order is SortOrder.DESC else column.asc()
    rows = db.execute(
        stmt.order_by(ordering, RoutePlan.id).offset(params.offset).limit(params.limit)
    ).scalars()
    return list(rows), int(total)
