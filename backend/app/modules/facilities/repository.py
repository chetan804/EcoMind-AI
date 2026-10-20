"""Database access for facilities. No business rules and no commits here."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.enums import SortOrder
from app.common.pagination import PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.modules.facilities.constants import FacilityStatus, FacilityType
from app.modules.facilities.models import Facility

_SORT_COLUMNS: dict[str, SQLColumnExpression[Any]] = {
    "name": func.lower(Facility.name),
    "code": Facility.code,
    "city": func.lower(Facility.city),
    "daily_capacity_kg": Facility.daily_capacity_kg,
    "created_at": Facility.created_at,
}


def get(db: Session, facility_id: uuid.UUID, *, for_update: bool = False) -> Facility | None:
    stmt = select(Facility).where(Facility.id == facility_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def add(db: Session, **fields: object) -> Facility:
    facility = Facility(**fields)
    db.add(facility)
    db.flush()
    return facility


def list_page(
    db: Session,
    params: PageParams,
    *,
    facility_type: FacilityType | None,
    status: FacilityStatus | None,
    city: str | None,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> tuple[list[Facility], int]:
    stmt = select(Facility)
    if facility_type is not None:
        stmt = stmt.where(Facility.facility_type == facility_type)
    if status is not None:
        stmt = stmt.where(Facility.status == status)
    if city:
        stmt = stmt.where(func.lower(Facility.city) == city.strip().lower())
    pattern = contains_pattern(q) if q else None
    if pattern is not None:
        stmt = stmt.where(
            or_(
                Facility.name.ilike(pattern, escape=LIKE_ESCAPE),
                Facility.code.ilike(pattern, escape=LIKE_ESCAPE),
                Facility.city.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _SORT_COLUMNS[sort_by]
    direction = column.desc() if order is SortOrder.DESC else column.asc()
    page = (
        stmt.order_by(direction.nulls_last(), Facility.id).limit(params.limit).offset(params.offset)
    )
    return list(db.execute(page).scalars()), total
