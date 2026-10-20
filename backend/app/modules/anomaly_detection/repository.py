"""Database access for anomaly alerts. No business rules and no commits here."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.enums import SortOrder
from app.common.pagination import PageParams
from app.modules.anomaly_detection.constants import AlertStatus, AnomalySeverity
from app.modules.anomaly_detection.models import AnomalyAlert

REFERENCE_PREFIX = "reference:"
_SEVERITY_RANK = case(
    (AnomalyAlert.severity == AnomalySeverity.CRITICAL, 3),
    (AnomalyAlert.severity == AnomalySeverity.WARNING, 2),
    else_=1,
)
_SORT_COLUMNS: dict[str, SQLColumnExpression[Any]] = {
    "detected_at": AnomalyAlert.detected_at,
    "window_start": AnomalyAlert.window_start,
    "severity": _SEVERITY_RANK,
    "status": AnomalyAlert.status,
}


def get(db: Session, alert_id: uuid.UUID, *, for_update: bool = False) -> AnomalyAlert | None:
    stmt = select(AnomalyAlert).where(AnomalyAlert.id == alert_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def find_existing(
    db: Session, *, metric: str, window_start: dt.datetime, detector_name: str
) -> AnomalyAlert | None:
    return db.execute(
        select(AnomalyAlert).where(
            AnomalyAlert.metric == metric,
            AnomalyAlert.window_start == window_start,
            AnomalyAlert.detector_name == detector_name,
        )
    ).scalar_one_or_none()


def add(db: Session, **fields: object) -> AnomalyAlert:
    alert = AnomalyAlert(**fields)
    db.add(alert)
    db.flush()
    return alert


def list_page(
    db: Session,
    params: PageParams,
    *,
    status: AlertStatus | None,
    severity: AnomalySeverity | None,
    metric: str | None,
    data_kind: str | None,
    sort_by: str,
    order: SortOrder,
) -> tuple[list[AnomalyAlert], int]:
    stmt = select(AnomalyAlert)
    if status is not None:
        stmt = stmt.where(AnomalyAlert.status == status)
    if severity is not None:
        stmt = stmt.where(AnomalyAlert.severity == severity)
    if metric is not None:
        stmt = stmt.where(AnomalyAlert.metric == metric)
    if data_kind == "platform":
        stmt = stmt.where(~AnomalyAlert.metric.like(REFERENCE_PREFIX + "%"))
    elif data_kind == "public_reference":
        stmt = stmt.where(AnomalyAlert.metric.like(REFERENCE_PREFIX + "%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _SORT_COLUMNS[sort_by]
    ordering = column.desc() if order is SortOrder.DESC else column.asc()
    rows = db.execute(
        stmt.order_by(ordering, AnomalyAlert.id).offset(params.offset).limit(params.limit)
    ).scalars()
    return list(rows), int(total)
