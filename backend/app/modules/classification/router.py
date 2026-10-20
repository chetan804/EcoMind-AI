"""Classification endpoints, mounted at ``/api/v1/classification``."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import AppSettings, DbSession
from app.common.pagination import Page, PageParams, page_params
from app.integrations.file_storage import FileStorage, LocalFileStorage
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import CurrentPrincipal, Principal, require_permissions
from app.modules.classification import service
from app.modules.classification.constants import ReviewStatus
from app.modules.classification.provider import RuntimeProvider, get_runtime_provider
from app.modules.classification.schemas import (
    ActiveModelOut,
    ModelVersionOut,
    PredictionCreate,
    PredictionOut,
    PredictionQuery,
    PredictionReview,
)

router = APIRouter()

CanPredict = Annotated[Principal, Depends(require_permissions("classification:predict"))]
CanReview = Annotated[Principal, Depends(require_permissions("classification:review"))]
CanManage = Annotated[Principal, Depends(require_permissions("classification:manage_models"))]
Pagination = Annotated[PageParams, Depends(page_params)]
Provider = Annotated[RuntimeProvider, Depends(get_runtime_provider)]


def get_storage(settings: AppSettings) -> FileStorage:
    return LocalFileStorage(settings.file_storage_local_path)


Storage = Annotated[FileStorage, Depends(get_storage)]


@router.get("/model", response_model=ActiveModelOut)
def active_model(db: DbSession, _: CurrentPrincipal) -> ActiveModelOut:
    """Which model (if any) answers predictions. ``active`` is null when none is active."""
    return service.active_model(db)


@router.get("/models", response_model=list[ModelVersionOut])
def list_models(db: DbSession, _: CanManage) -> list[ModelVersionOut]:
    return service.list_models(db)


@router.post("/models/{version_id}/activate", response_model=ModelVersionOut)
def activate_model(
    version_id: uuid.UUID,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    principal: CanManage,
) -> ModelVersionOut:
    """Make a registered version active (re-verifies its artifacts first)."""
    return service.activate_model(
        db,
        settings.model_artifacts_dir,
        version_id,
        actor_id=principal.user_id,
        context=RequestContext.from_request(request),
    )


@router.post("/predictions", response_model=PredictionOut, status_code=status.HTTP_201_CREATED)
def create_prediction(
    payload: PredictionCreate,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    storage: Storage,
    provider: Provider,
    principal: CanPredict,
) -> PredictionOut:
    """Classify an uploaded image (``media_id`` from ``POST /waste-reports/media``).

    503 ``no_active_model`` when no model is active (nothing is ever faked). Asking again for
    the same image and model returns the stored prediction (200, ``Idempotent-Replayed: true``).
    """
    prediction, created = service.predict(
        db,
        storage,
        provider,
        settings.model_artifacts_dir,
        principal,
        payload.media_id,
        context=RequestContext.from_request(request),
    )
    if not created:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return prediction


@router.get("/predictions", response_model=Page[PredictionOut])
def list_predictions(
    db: DbSession,
    _: CanReview,
    params: Pagination,
    needs_review: bool | None = None,
    review_status: Annotated[ReviewStatus | None, Query()] = None,
    model_version_id: uuid.UUID | None = None,
) -> Page[PredictionOut]:
    query = PredictionQuery(
        needs_review=needs_review, review_status=review_status, model_version_id=model_version_id
    )
    return service.list_predictions(db, query, params)


@router.get("/predictions/{prediction_id}", response_model=PredictionOut)
def get_prediction(prediction_id: uuid.UUID, db: DbSession, principal: CanPredict) -> PredictionOut:
    return service.get_prediction(db, principal, prediction_id)


@router.post("/predictions/{prediction_id}/review", response_model=PredictionOut)
def review_prediction(
    prediction_id: uuid.UUID,
    payload: PredictionReview,
    request: Request,
    db: DbSession,
    principal: CanReview,
) -> PredictionOut:
    """Confirm, correct or reject a prediction. The original model output is kept unchanged."""
    return service.review_prediction(
        db, principal, prediction_id, payload, context=RequestContext.from_request(request)
    )
