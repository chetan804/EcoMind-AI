"""Database access for recovery records. No business rules and no commits here."""

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
from app.modules.circular_economy.constants import RecoveryMethod, VerificationStatus
from app.modules.circular_economy.models import RecoveryRecord
from app.modules.sorting_guide.models import MaterialCategory

_SORT: dict[str, SQLColumnExpression[Any]] = {
    "processed_at": RecoveryRecord.processed_at,
    "created_at": RecoveryRecord.created_at,
    "input_weight_kg": RecoveryRecord.input_weight_kg,
    "recovered_weight_kg": RecoveryRecord.recovered_weight_kg,
}


def get(db: Session, record_id: uuid.UUID, *, for_update: bool = False) -> RecoveryRecord | None:
    stmt = select(RecoveryRecord).where(RecoveryRecord.id == record_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def add(db: Session, **fields: object) -> RecoveryRecord:
    record = RecoveryRecord(**fields)
    db.add(record)
    db.flush()
    return record


def _filtered(
    stmt: Any,
    *,
    facility_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    method: RecoveryMethod | None,
    status: VerificationStatus | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> Any:  # a Select with any column tuple
    if facility_id is not None:
        stmt = stmt.where(RecoveryRecord.facility_id == facility_id)
    if category_id is not None:
        stmt = stmt.where(RecoveryRecord.material_category_id == category_id)
    if method is not None:
        stmt = stmt.where(RecoveryRecord.recovery_method == method)
    if status is not None:
        stmt = stmt.where(RecoveryRecord.verification_status == status)
    if date_from is not None:
        start = dt.datetime.combine(date_from, dt.time.min, tzinfo=dt.UTC)
        stmt = stmt.where(RecoveryRecord.processed_at >= start)
    if date_to is not None:
        end = dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min, tzinfo=dt.UTC)
        stmt = stmt.where(RecoveryRecord.processed_at < end)
    return stmt


def list_page(
    db: Session,
    params: PageParams,
    *,
    facility_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    method: RecoveryMethod | None,
    status: VerificationStatus | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    sort_by: str,
    order: SortOrder,
) -> tuple[list[RecoveryRecord], int]:
    stmt = _filtered(
        select(RecoveryRecord),
        facility_id=facility_id,
        category_id=category_id,
        method=method,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _SORT[sort_by]
    direction = column.desc() if order is SortOrder.DESC else column.asc()
    rows = db.execute(
        stmt.order_by(direction, RecoveryRecord.id).offset(params.offset).limit(params.limit)
    ).scalars()
    return list(rows), int(total)


def status_counts(
    db: Session,
    *,
    facility_id: uuid.UUID | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> dict[VerificationStatus, int]:
    stmt = _filtered(
        select(RecoveryRecord.verification_status, func.count()),
        facility_id=facility_id,
        category_id=None,
        method=None,
        status=None,
        date_from=date_from,
        date_to=date_to,
    ).group_by(RecoveryRecord.verification_status)
    return {s: int(n) for s, n in db.execute(stmt).all()}


def verified_totals(
    db: Session,
    *,
    group: str,
    facility_id: uuid.UUID | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> list[tuple[str, str, int, decimal.Decimal, decimal.Decimal]]:
    """Verified records only, grouped by ``category`` or ``method``."""
    if group == "category":
        key, label = MaterialCategory.code, MaterialCategory.name
    else:
        key, label = RecoveryRecord.recovery_method, RecoveryRecord.recovery_method
    stmt = (
        select(
            key,
            label,
            func.count(),
            func.coalesce(func.sum(RecoveryRecord.input_weight_kg), 0),
            func.coalesce(func.sum(RecoveryRecord.recovered_weight_kg), 0),
        )
        .select_from(RecoveryRecord)
        .join(MaterialCategory, MaterialCategory.id == RecoveryRecord.material_category_id)
        .where(RecoveryRecord.verification_status == VerificationStatus.VERIFIED)
    )
    stmt = _filtered(
        stmt,
        facility_id=facility_id,
        category_id=None,
        method=None,
        status=None,
        date_from=date_from,
        date_to=date_to,
    )
    rows = db.execute(stmt.group_by(key, label).order_by(key)).all()
    return [(str(row[0]), str(row[1]), int(row[2]), row[3], row[4]) for row in rows]
