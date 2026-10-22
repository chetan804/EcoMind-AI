from __future__ import annotations

from app.core.exceptions import AppError


class NoActiveModelError(AppError):
    """No model version is active, so there is nothing honest to answer with."""

    status_code = 503
    code = "no_active_model"


class ModelUnavailableError(AppError):
    """The active model's artifacts are missing or fail their integrity check."""

    status_code = 503
    code = "model_unavailable"


class InvalidImageError(AppError):
    status_code = 422
    code = "invalid_image"


class PredictionAlreadyReviewedError(AppError):
    status_code = 409
    code = "prediction_already_reviewed"


class InvalidReviewError(AppError):
    status_code = 422
    code = "invalid_review"


class ModelVersionNotFoundError(AppError):
    status_code = 404
    code = "model_version_not_found"


class ModelNotApprovedError(AppError):
    """The artifact's own release record does not approve it for activation (fail closed)."""

    status_code = 409
    code = "model_not_approved"
