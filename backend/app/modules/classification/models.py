"""Classification model versions and predictions. Owned by the ``classification`` module.

A prediction keeps the *identified object* (``object_label``) separate from the *waste-material
category* (``material_category_id``); disposal guidance is looked up from ``sorting_guide`` via
the category and is not stored here. Confidence values are those reported by the model version
that produced the prediction; they are never fabricated.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.classification.constants import ModelVersionStatus, ReviewStatus


class ClassificationModelVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "classification_model_versions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_classification_model_versions_name_version"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[ModelVersionStatus] = mapped_column(
        enum_column(ModelVersionStatus),
        nullable=False,
        server_default=ModelVersionStatus.CANDIDATE.value,
    )
    framework: Mapped[str | None] = mapped_column(String(50))
    # SHA-256 of the artifact manifest in ml/model_registry; ties a row to exact artifacts.
    artifact_manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    # Evaluation summary copied from the model card; the evidence lives in docs/ml/model-cards.
    evaluation_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    trained_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ClassificationPrediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "classification_predictions"
    __table_args__ = (
        UniqueConstraint(
            "media_asset_id",
            "model_version_id",
            name="uq_classification_predictions_media_asset_id_model_version_id",
        ),
        CheckConstraint("object_confidence BETWEEN 0 AND 1", name="object_confidence_range"),
        CheckConstraint("material_confidence BETWEEN 0 AND 1", name="material_confidence_range"),
        CheckConstraint(
            "(review_status = 'unreviewed') = (reviewed_at IS NULL)",
            name="review_timestamp_consistent",
        ),
        CheckConstraint(
            "(review_status = 'corrected') = (reviewed_material_category_id IS NOT NULL)",
            name="correction_has_category",
        ),
    )

    media_asset_id: Mapped[uuid.UUID] = fk_uuid("media_assets.id", ondelete="CASCADE")
    model_version_id: Mapped[uuid.UUID] = fk_uuid("classification_model_versions.id")
    object_label: Mapped[str | None] = mapped_column(String(200))
    object_confidence: Mapped[decimal.Decimal | None] = mapped_column(Numeric(5, 4))
    material_category_id: Mapped[uuid.UUID] = fk_uuid("material_categories.id")
    material_confidence: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    review_status: Mapped[ReviewStatus] = mapped_column(
        enum_column(ReviewStatus),
        nullable=False,
        index=True,
        server_default=ReviewStatus.UNREVIEWED.value,
    )
    reviewed_material_category_id: Mapped[uuid.UUID | None] = fk_uuid(
        "material_categories.id", nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
