"""Database access for material passports. No business rules and no commits here."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.enums import SortOrder
from app.common.pagination import PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.modules.material_passports.constants import PassportStatus
from app.modules.material_passports.models import CustodyEvent, MaterialPassport

_SORT: dict[str, SQLColumnExpression[Any]] = {
    "created_at": MaterialPassport.created_at,
    "weight_kg": MaterialPassport.weight_kg,
    "passport_code": MaterialPassport.passport_code,
    "status": MaterialPassport.status,
}


def get(
    db: Session, passport_id: uuid.UUID, *, for_update: bool = False
) -> MaterialPassport | None:
    stmt = select(MaterialPassport).where(MaterialPassport.id == passport_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def get_by_code(db: Session, code: str) -> MaterialPassport | None:
    return db.execute(
        select(MaterialPassport).where(MaterialPassport.passport_code == code)
    ).scalar_one_or_none()


def add(db: Session, **fields: object) -> MaterialPassport:
    passport = MaterialPassport(**fields)
    db.add(passport)
    db.flush()
    return passport


def add_event(db: Session, **fields: object) -> CustodyEvent:
    event = CustodyEvent(**fields)
    db.add(event)
    db.flush()
    return event


def events(db: Session, passport_id: uuid.UUID) -> list[CustodyEvent]:
    return list(
        db.execute(
            select(CustodyEvent)
            .where(CustodyEvent.material_passport_id == passport_id)
            .order_by(CustodyEvent.sequence)
        ).scalars()
    )


def passport_for_recovery(
    db: Session, record_id: uuid.UUID, *, exclude: uuid.UUID | None = None
) -> MaterialPassport | None:
    stmt = select(MaterialPassport).where(MaterialPassport.recovery_record_id == record_id)
    if exclude is not None:
        stmt = stmt.where(MaterialPassport.id != exclude)
    return db.execute(stmt).scalars().first()


def list_page(
    db: Session,
    params: PageParams,
    *,
    status: PassportStatus | None,
    category_id: uuid.UUID | None,
    facility_id: uuid.UUID | None,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> tuple[list[MaterialPassport], int]:
    stmt = select(MaterialPassport)
    if status is not None:
        stmt = stmt.where(MaterialPassport.status == status)
    if category_id is not None:
        stmt = stmt.where(MaterialPassport.material_category_id == category_id)
    if facility_id is not None:
        stmt = stmt.where(MaterialPassport.current_facility_id == facility_id)
    pattern = contains_pattern(q) if q else None
    if pattern is not None:
        stmt = stmt.where(MaterialPassport.passport_code.ilike(pattern, escape=LIKE_ESCAPE))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _SORT[sort_by]
    direction = column.desc() if order is SortOrder.DESC else column.asc()
    rows = db.execute(
        stmt.order_by(direction, MaterialPassport.id).offset(params.offset).limit(params.limit)
    ).scalars()
    return list(rows), int(total)
