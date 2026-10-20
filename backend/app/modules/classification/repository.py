"""Database access for classification. No business rules and no commits here."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.classification.constants import ModelVersionStatus
from app.modules.classification.models import ClassificationModelVersion, ClassificationPrediction
from app.modules.classification.schemas import PredictionQuery
from app.modules.sorting_guide.models import MaterialCategory
from app.modules.waste_reports.models import MediaAsset


def active_version(db: Session) -> ClassificationModelVersion | None:
    return db.execute(
        select(ClassificationModelVersion).where(
            ClassificationModelVersion.status == ModelVersionStatus.ACTIVE
        )
    ).scalar_one_or_none()


def get_version(
    db: Session, version_id: uuid.UUID, *, for_update: bool = False
) -> ClassificationModelVersion | None:
    stmt = select(ClassificationModelVersion).where(ClassificationModelVersion.id == version_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def find_version(db: Session, name: str, version: str) -> ClassificationModelVersion | None:
    return db.execute(
        select(ClassificationModelVersion).where(
            ClassificationModelVersion.name == name, ClassificationModelVersion.version == version
        )
    ).scalar_one_or_none()


def list_versions(db: Session) -> Sequence[ClassificationModelVersion]:
    return (
        db.execute(
            select(ClassificationModelVersion).order_by(
                ClassificationModelVersion.created_at.desc()
            )
        )
        .scalars()
        .all()
    )


def categories(db: Session) -> dict[uuid.UUID, MaterialCategory]:
    return {c.id: c for c in db.execute(select(MaterialCategory)).scalars()}


def category_by_code(db: Session, code: str) -> MaterialCategory | None:
    return db.execute(
        select(MaterialCategory).where(MaterialCategory.code == code, MaterialCategory.is_active)
    ).scalar_one_or_none()


def get_prediction(
    db: Session, prediction_id: uuid.UUID, *, for_update: bool = False
) -> ClassificationPrediction | None:
    stmt = select(ClassificationPrediction).where(ClassificationPrediction.id == prediction_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def prediction_for(
    db: Session, media_id: uuid.UUID, version_id: uuid.UUID
) -> ClassificationPrediction | None:
    return db.execute(
        select(ClassificationPrediction).where(
            ClassificationPrediction.media_asset_id == media_id,
            ClassificationPrediction.model_version_id == version_id,
        )
    ).scalar_one_or_none()


def media_owner(db: Session, media_id: uuid.UUID) -> uuid.UUID | None:
    return db.execute(
        select(MediaAsset.uploaded_by_id).where(MediaAsset.id == media_id)
    ).scalar_one_or_none()


def versions_by_id(db: Session) -> dict[uuid.UUID, ClassificationModelVersion]:
    return {v.id: v for v in list_versions(db)}


def list_predictions(
    db: Session, query: PredictionQuery, params: PageParams
) -> tuple[list[ClassificationPrediction], int]:
    stmt = select(ClassificationPrediction)
    if query.needs_review is not None:
        stmt = stmt.where(ClassificationPrediction.needs_review == query.needs_review)
    if query.review_status is not None:
        stmt = stmt.where(ClassificationPrediction.review_status == query.review_status)
    if query.model_version_id is not None:
        stmt = stmt.where(ClassificationPrediction.model_version_id == query.model_version_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(ClassificationPrediction.created_at.desc(), ClassificationPrediction.id)
        .offset(params.offset)
        .limit(params.limit)
    ).scalars()
    return list(rows), total
