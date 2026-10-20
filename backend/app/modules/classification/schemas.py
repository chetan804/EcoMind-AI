from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.classification.constants import ModelVersionStatus, ReviewStatus

Notes = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class CategoryRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class ModelVersionOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    status: ModelVersionStatus
    framework: str | None
    artifact_manifest_sha256: str | None
    evaluation_metrics: dict[str, Any] | None
    trained_at: dt.datetime | None
    activated_at: dt.datetime | None


class ActiveModelOut(BaseModel):
    """``active`` is null when no model has been activated: the API then refuses to predict."""

    active: ModelVersionOut | None
    scope: Literal["material_category"] = "material_category"
    note: str = (
        "Predicts the material category only. No object label is produced. "
        "Scores come from studio-style photographs. On one real-world dataset (RealWaste, "
        "facility photos) the first model reached about 45% accuracy, so treat every prediction "
        "as a suggestion for a person to check."
    )


class PredictionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_id: uuid.UUID


class ReviewOut(BaseModel):
    status: ReviewStatus
    corrected_category: CategoryRef | None
    reviewed_by_id: uuid.UUID | None
    reviewed_at: dt.datetime | None
    notes: str | None


class PredictionOut(BaseModel):
    id: uuid.UUID
    media_asset_id: uuid.UUID
    model_name: str
    model_version: str
    material_category: CategoryRef
    confidence: float = Field(ge=0, le=1, description="Calibrated probability of the category")
    class_probabilities: dict[str, float]
    needs_review: bool
    review_reasons: list[str]
    novelty_similarity: float | None
    inference_ms: float | None
    object_label: str | None = Field(
        description="Always null for the current model (no object-level labels)"
    )
    review: ReviewOut
    created_at: dt.datetime


class PredictionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["confirmed", "corrected", "rejected"]
    material_category_code: Annotated[str, StringConstraints(max_length=64)] | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def _code_matches_decision(self) -> Self:
        if self.decision == "corrected" and not self.material_category_code:
            raise ValueError("material_category_code is required when decision is 'corrected'")
        if self.decision != "corrected" and self.material_category_code:
            raise ValueError("material_category_code is only allowed when decision is 'corrected'")
        return self


class PredictionQuery(BaseModel):
    needs_review: bool | None = None
    review_status: ReviewStatus | None = None
    model_version_id: uuid.UUID | None = None
