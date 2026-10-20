from __future__ import annotations

from app.core.exceptions import AppError


class InvalidTransitionError(AppError):
    status_code = 409
    code = "invalid_status_transition"


class IdempotencyKeyReusedError(AppError):
    status_code = 409
    code = "idempotency_key_reused"


class UploadQuotaExceededError(AppError):
    status_code = 409
    code = "upload_quota_exceeded"


class InvalidMediaError(AppError):
    """An attachment id is unknown, not the caller's, or already used (deliberately one error)."""

    status_code = 422
    code = "invalid_media"
