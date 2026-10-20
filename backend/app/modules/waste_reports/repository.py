"""Database access for waste reports and media. No business rules and no commits here."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLColumnExpression

from app.common.enums import SortOrder
from app.common.pagination import PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.modules.waste_reports.models import MediaAsset, WasteReport
from app.modules.waste_reports.schemas import WasteReportQuery

_SORT_COLUMNS: dict[str, SQLColumnExpression[Any]] = {
    "reported_at": WasteReport.reported_at,
    "title": func.lower(WasteReport.title),
    "status": WasteReport.status,
    "estimated_weight_kg": WasteReport.estimated_weight_kg,
}


def get(db: Session, report_id: uuid.UUID, *, for_update: bool = False) -> WasteReport | None:
    stmt = select(WasteReport).where(WasteReport.id == report_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def get_by_idempotency_key(db: Session, reporter_id: uuid.UUID, key: str) -> WasteReport | None:
    return db.execute(
        select(WasteReport).where(
            WasteReport.reporter_id == reporter_id, WasteReport.idempotency_key == key
        )
    ).scalar_one_or_none()


def add(db: Session, **fields: object) -> WasteReport:
    report = WasteReport(**fields)
    db.add(report)
    db.flush()
    return report


def _filtered(
    query: WasteReportQuery, *, reporter_id: uuid.UUID | None
) -> Select[tuple[uuid.UUID]]:
    stmt: Select[tuple[uuid.UUID]] = select(WasteReport.id)
    if reporter_id is not None:
        stmt = stmt.where(WasteReport.reporter_id == reporter_id)
    if query.status is not None:
        stmt = stmt.where(WasteReport.status == query.status)
    if query.reported_from is not None:
        stmt = stmt.where(WasteReport.reported_at >= query.reported_from)
    if query.reported_to is not None:
        stmt = stmt.where(WasteReport.reported_at <= query.reported_to)
    pattern = contains_pattern(query.q) if query.q else None
    if pattern is not None:
        stmt = stmt.where(
            or_(
                WasteReport.title.ilike(pattern, escape=LIKE_ESCAPE),
                WasteReport.description.ilike(pattern, escape=LIKE_ESCAPE),
                WasteReport.address_text.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    return stmt


def list_page(
    db: Session,
    query: WasteReportQuery,
    params: PageParams,
    *,
    reporter_id: uuid.UUID | None,
) -> tuple[list[WasteReport], int]:
    """One page plus the total number of matches. Ordering is total (ties broken by id) so pages
    never repeat or skip a row."""
    filtered = _filtered(query, reporter_id=reporter_id)
    total = db.execute(select(func.count()).select_from(filtered.subquery())).scalar_one()
    column = _SORT_COLUMNS[query.sort_by]
    direction = column.desc() if query.order is SortOrder.DESC else column.asc()
    stmt = (
        select(WasteReport)
        .where(WasteReport.id.in_(filtered))
        .order_by(direction.nulls_last(), WasteReport.id.desc())
        .limit(params.limit)
        .offset(params.offset)
    )
    return list(db.execute(stmt).scalars()), total


def media_by_report(
    db: Session, report_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[MediaAsset]]:
    grouped: dict[uuid.UUID, list[MediaAsset]] = defaultdict(list)
    if not report_ids:
        return grouped
    rows = db.execute(
        select(MediaAsset)
        .where(MediaAsset.waste_report_id.in_(report_ids))
        .order_by(MediaAsset.created_at, MediaAsset.id)
    ).scalars()
    for media in rows:
        if media.waste_report_id is not None:
            grouped[media.waste_report_id].append(media)
    return grouped


def get_media(db: Session, media_id: uuid.UUID) -> MediaAsset | None:
    return db.execute(select(MediaAsset).where(MediaAsset.id == media_id)).scalar_one_or_none()


def lock_media(db: Session, media_ids: Sequence[uuid.UUID]) -> list[MediaAsset]:
    """Lock the rows so two concurrent submissions cannot attach the same upload twice."""
    if not media_ids:
        return []
    stmt = select(MediaAsset).where(MediaAsset.id.in_(media_ids)).order_by(MediaAsset.id)
    return list(db.execute(stmt.with_for_update()).scalars())


def count_unattached(db: Session, user_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).where(
            MediaAsset.uploaded_by_id == user_id, MediaAsset.waste_report_id.is_(None)
        )
    ).scalar_one()


def add_media(db: Session, **fields: object) -> MediaAsset:
    media = MediaAsset(**fields)
    db.add(media)
    db.flush()
    return media
