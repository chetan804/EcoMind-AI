"""Database access for the sorting guide. No business rules and no commits here."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.pagination import PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.modules.sorting_guide.constants import DisposalMethod
from app.modules.sorting_guide.models import MaterialCategory, SortingGuidance

_GUIDANCE_SORT: dict[str, SQLColumnExpression[Any]] = {
    "title": func.lower(SortingGuidance.title),
    "created_at": SortingGuidance.created_at,
    "disposal_method": SortingGuidance.disposal_method,
}


def get_category(db: Session, category_id: uuid.UUID) -> MaterialCategory | None:
    return db.get(MaterialCategory, category_id)


def get_category_by_code(db: Session, code: str) -> MaterialCategory | None:
    return db.execute(
        select(MaterialCategory).where(MaterialCategory.code == code)
    ).scalar_one_or_none()


def add_category(db: Session, **fields: object) -> MaterialCategory:
    row = MaterialCategory(**fields)
    db.add(row)
    db.flush()
    return row


def list_categories(
    db: Session, params: PageParams, *, include_inactive: bool, q: str | None
) -> tuple[list[tuple[MaterialCategory, int]], int]:
    stmt = select(MaterialCategory)
    if not include_inactive:
        stmt = stmt.where(MaterialCategory.is_active.is_(True))
    pattern = contains_pattern(q) if q else None
    if pattern is not None:
        stmt = stmt.where(
            or_(
                MaterialCategory.name.ilike(pattern, escape=LIKE_ESCAPE),
                MaterialCategory.code.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(func.lower(MaterialCategory.name), MaterialCategory.id)
            .limit(params.limit)
            .offset(params.offset)
        ).scalars()
    )
    counts = guidance_counts(db, [r.id for r in rows])
    return [(r, counts.get(r.id, 0)) for r in rows], int(total)


def guidance_counts(db: Session, category_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not category_ids:
        return {}
    stmt = (
        select(SortingGuidance.material_category_id, func.count())
        .where(
            SortingGuidance.material_category_id.in_(category_ids),
            SortingGuidance.is_active.is_(True),
        )
        .group_by(SortingGuidance.material_category_id)
    )
    return {cid: int(n) for cid, n in db.execute(stmt).all()}


def get_guidance(db: Session, guidance_id: uuid.UUID) -> SortingGuidance | None:
    return db.get(SortingGuidance, guidance_id)


def add_guidance(db: Session, **fields: object) -> SortingGuidance:
    row = SortingGuidance(**fields)
    db.add(row)
    db.flush()
    return row


def list_guidance(
    db: Session,
    params: PageParams,
    *,
    category_id: uuid.UUID | None,
    disposal_method: DisposalMethod | None,
    include_inactive: bool,
    q: str | None,
    sort_by: str,
    descending: bool,
) -> tuple[list[tuple[SortingGuidance, MaterialCategory]], int]:
    stmt = select(SortingGuidance, MaterialCategory).join(
        MaterialCategory, MaterialCategory.id == SortingGuidance.material_category_id
    )
    if not include_inactive:
        stmt = stmt.where(SortingGuidance.is_active.is_(True), MaterialCategory.is_active.is_(True))
    if category_id is not None:
        stmt = stmt.where(SortingGuidance.material_category_id == category_id)
    if disposal_method is not None:
        stmt = stmt.where(SortingGuidance.disposal_method == disposal_method)
    pattern = contains_pattern(q) if q else None
    if pattern is not None:
        stmt = stmt.where(
            or_(
                SortingGuidance.title.ilike(pattern, escape=LIKE_ESCAPE),
                SortingGuidance.instructions.ilike(pattern, escape=LIKE_ESCAPE),
                MaterialCategory.name.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    column = _GUIDANCE_SORT[sort_by]
    direction = column.desc() if descending else column.asc()
    rows = db.execute(
        stmt.order_by(direction, SortingGuidance.id).limit(params.limit).offset(params.offset)
    ).all()
    return [(g, c) for g, c in rows], int(total)
