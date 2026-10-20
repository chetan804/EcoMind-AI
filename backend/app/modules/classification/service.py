"""Classification business rules: predict, review, register and activate model versions."""

from __future__ import annotations

import datetime as dt
import decimal
import json
import uuid
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.common.time import utc_now
from app.core.exceptions import ConflictError, NotFoundError
from app.integrations.file_storage import FileStorage
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.classification import repository
from app.modules.classification.constants import ModelVersionStatus, ReviewStatus
from app.modules.classification.errors import (
    InvalidReviewError,
    ModelUnavailableError,
    ModelVersionNotFoundError,
    NoActiveModelError,
    PredictionAlreadyReviewedError,
)
from app.modules.classification.models import ClassificationModelVersion, ClassificationPrediction
from app.modules.classification.provider import (
    RuntimeProvider,
    artifact_dir,
    load_verified,
)
from app.modules.classification.runtime import ClassifierRuntime, sha256_file
from app.modules.classification.schemas import (
    ActiveModelOut,
    CategoryRef,
    ModelVersionOut,
    PredictionOut,
    PredictionQuery,
    PredictionReview,
    ReviewOut,
)
from app.modules.sorting_guide.models import MaterialCategory
from app.modules.waste_reports import service as reports_service

REVIEW = "classification:review"
READ_ALL_MEDIA = "waste_reports:read_all"
_Q4 = decimal.Decimal("0.0001")


def _dec4(value: float) -> decimal.Decimal:
    return decimal.Decimal(str(round(value, 4))).quantize(_Q4)


def _version_out(row: ClassificationModelVersion) -> ModelVersionOut:
    return ModelVersionOut.model_validate(row, from_attributes=True)


# -- model versions ------------------------------------------------------------------------------
def active_model(db: Session) -> ActiveModelOut:
    row = repository.active_version(db)
    return ActiveModelOut(active=_version_out(row) if row else None)


def list_models(db: Session) -> list[ModelVersionOut]:
    return [_version_out(v) for v in repository.list_versions(db)]


def register_model(
    db: Session, artifacts_dir: Path, version: str, *, context: RequestContext | None = None
) -> ClassificationModelVersion:
    """Register (as ``candidate``) a trained artifact found under ``MODEL_ARTIFACTS_DIR``.

    The artifact is fully loaded and its hashes verified before a row is written. Registering
    the same (name, version) again is a no-op if the artifact is identical and an error if not.
    """
    model_json = artifact_dir(artifacts_dir, version) / "model.json"
    if not model_json.is_file():
        raise ModelUnavailableError(f"No artifact at {model_json.parent}")
    manifest = json.loads(model_json.read_text())
    digest = sha256_file(model_json)
    load_verified(artifacts_dir, manifest["name"], manifest["version"], digest)
    existing = repository.find_version(db, manifest["name"], manifest["version"])
    if existing is not None:
        if existing.artifact_manifest_sha256 != digest:
            raise ConflictError("This version is already registered with different artifacts")
        return existing
    trained_at = manifest.get("trained_at_utc")
    row = ClassificationModelVersion(
        name=manifest["name"],
        version=manifest["version"],
        status=ModelVersionStatus.CANDIDATE,
        framework="tflite backbone + numpy linear head",
        artifact_manifest_sha256=digest,
        evaluation_metrics=manifest.get("evaluation"),
        trained_at=dt.datetime.fromisoformat(trained_at.replace("Z", "+00:00"))
        if trained_at
        else None,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action="classification.model_registered",
        entity_type="classification_model_version",
        entity_id=row.id,
        context=context,
        changes={"name": row.name, "version": row.version, "sha256": digest},
    )
    db.commit()
    return row


def activate_model(
    db: Session,
    artifacts_dir: Path,
    version_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None,
    context: RequestContext,
) -> ModelVersionOut:
    """Make a registered version the single active one (the previous active becomes retired).

    The artifact is re-verified first, so a version that cannot be served is never activated.
    """
    row = repository.get_version(db, version_id, for_update=True)
    if row is None:
        raise ModelVersionNotFoundError("Model version not found")
    load_verified(artifacts_dir, row.name, row.version, row.artifact_manifest_sha256)
    if row.status != ModelVersionStatus.ACTIVE:
        previous = repository.active_version(db)
        if previous is not None:
            previous.status = ModelVersionStatus.RETIRED
            db.flush()  # free the one-active slot before taking it
        row.status = ModelVersionStatus.ACTIVE
        row.activated_at = utc_now()
        audit.record(
            db,
            action="classification.model_activated",
            entity_type="classification_model_version",
            entity_id=row.id,
            actor_id=actor_id,
            context=context,
            changes={"version": row.version, "replaced": previous.version if previous else None},
        )
        db.commit()
        db.refresh(row)
    return _version_out(row)


# -- predictions ---------------------------------------------------------------------------------
def _lookups(
    db: Session,
) -> tuple[dict[uuid.UUID, MaterialCategory], dict[uuid.UUID, ClassificationModelVersion]]:
    return repository.categories(db), repository.versions_by_id(db)


def _ref(category: MaterialCategory) -> CategoryRef:
    return CategoryRef(id=category.id, code=category.code, name=category.name)


def _present(
    prediction: ClassificationPrediction,
    cats: dict[uuid.UUID, MaterialCategory],
    versions: dict[uuid.UUID, ClassificationModelVersion],
) -> PredictionOut:
    corrected_id = prediction.reviewed_material_category_id
    model = versions[prediction.model_version_id]
    return PredictionOut(
        id=prediction.id,
        media_asset_id=prediction.media_asset_id,
        model_name=model.name,
        model_version=model.version,
        material_category=_ref(cats[prediction.material_category_id]),
        confidence=float(prediction.material_confidence),
        class_probabilities=prediction.class_probabilities,
        needs_review=prediction.needs_review,
        review_reasons=list(prediction.review_reasons),
        novelty_similarity=float(prediction.novelty_similarity)
        if prediction.novelty_similarity is not None
        else None,
        inference_ms=float(prediction.inference_ms)
        if prediction.inference_ms is not None
        else None,
        object_label=prediction.object_label,
        review=ReviewOut(
            status=prediction.review_status,
            corrected_category=_ref(cats[corrected_id]) if corrected_id else None,
            reviewed_by_id=prediction.reviewed_by_id,
            reviewed_at=prediction.reviewed_at,
            notes=prediction.review_notes,
        ),
        created_at=prediction.created_at,
    )


def _one(db: Session, prediction: ClassificationPrediction) -> PredictionOut:
    return _present(prediction, *_lookups(db))


def predict(
    db: Session,
    storage: FileStorage,
    provider: RuntimeProvider,
    artifacts_dir: Path,
    principal: Principal,
    media_id: uuid.UUID,
    *,
    context: RequestContext,
) -> tuple[PredictionOut, bool]:
    """Classify an uploaded image with the ACTIVE model. Returns ``(prediction, created)``.

    Re-requesting the same image for the same model returns the stored prediction instead of
    recomputing it (a prediction is a recorded fact about a model version).
    """
    model = repository.active_version(db)
    if model is None:
        raise NoActiveModelError("No classification model is active")
    data, media = reports_service.read_media(db, storage, principal, media_id)
    existing = repository.prediction_for(db, media.id, model.id)
    if existing is not None:
        return _one(db, existing), False
    runtime: ClassifierRuntime = provider.runtime_for(model, artifacts_dir)
    raw = runtime.predict_bytes(data)
    category = repository.category_by_code(
        db, runtime.manifest.get("material_category_codes", {}).get(raw.label, raw.label)
    )
    if category is None:
        raise ModelUnavailableError("The predicted category is not configured on this server")
    prediction = ClassificationPrediction(
        media_asset_id=media.id,
        model_version_id=model.id,
        object_label=None,
        object_confidence=None,
        material_category_id=category.id,
        material_confidence=_dec4(min(max(raw.confidence, 0.0), 1.0)),
        class_probabilities={k: round(v, 6) for k, v in raw.probabilities.items()},
        needs_review=raw.needs_review,
        review_reasons=raw.review_reasons,
        novelty_similarity=_dec4(min(max(raw.novelty_similarity, 0.0), 1.0)),
        inference_ms=decimal.Decimal(str(round(raw.inference_ms, 1))),
    )
    db.add(prediction)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()  # a concurrent request stored it first: return that one
        winner = repository.prediction_for(db, media.id, model.id)
        if winner is None:
            raise
        return _one(db, winner), False
    audit.record(
        db,
        action="classification.predicted",
        entity_type="classification_prediction",
        entity_id=prediction.id,
        actor_id=principal.user_id,
        context=context,
        changes={
            "model_version": model.version,
            "category": category.code,
            "confidence": float(prediction.material_confidence),
            "needs_review": raw.needs_review,
        },
    )
    db.commit()
    db.refresh(prediction)
    return _one(db, prediction), True


def _can_see(db: Session, principal: Principal, prediction: ClassificationPrediction) -> bool:
    if principal.has(REVIEW) or principal.has(READ_ALL_MEDIA):
        return True
    return repository.media_owner(db, prediction.media_asset_id) == principal.user_id


def get_prediction(db: Session, principal: Principal, prediction_id: uuid.UUID) -> PredictionOut:
    prediction = repository.get_prediction(db, prediction_id)
    if prediction is None or not _can_see(db, principal, prediction):
        raise NotFoundError("Prediction not found")
    return _one(db, prediction)


def list_predictions(
    db: Session, query: PredictionQuery, params: PageParams
) -> Page[PredictionOut]:
    rows, total = repository.list_predictions(db, query, params)
    cats, versions = _lookups(db)
    return Page.build([_present(r, cats, versions) for r in rows], total, params)


def review_prediction(
    db: Session,
    principal: Principal,
    prediction_id: uuid.UUID,
    payload: PredictionReview,
    *,
    context: RequestContext,
) -> PredictionOut:
    """Record a human decision. One review per prediction; the original model output is kept."""
    prediction = repository.get_prediction(db, prediction_id, for_update=True)
    if prediction is None:
        raise NotFoundError("Prediction not found")
    if prediction.review_status != ReviewStatus.UNREVIEWED:
        raise PredictionAlreadyReviewedError("This prediction has already been reviewed")
    corrected_id: uuid.UUID | None = None
    if payload.decision == "corrected":
        category = (
            repository.category_by_code(db, payload.material_category_code)
            if payload.material_category_code
            else None
        )
        if category is None:
            raise InvalidReviewError("Unknown material category")
        if category.id == prediction.material_category_id:
            raise InvalidReviewError("The correction equals the prediction; use 'confirmed'")
        corrected_id = category.id
    prediction.review_status = ReviewStatus(payload.decision)
    prediction.reviewed_material_category_id = corrected_id
    prediction.reviewed_by_id = principal.user_id
    prediction.reviewed_at = utc_now()
    prediction.review_notes = payload.notes
    audit.record(
        db,
        action="classification.reviewed",
        entity_type="classification_prediction",
        entity_id=prediction.id,
        actor_id=principal.user_id,
        context=context,
        changes={"decision": payload.decision, "corrected_to": payload.material_category_code},
    )
    db.commit()
    db.refresh(prediction)
    return _one(db, prediction)
