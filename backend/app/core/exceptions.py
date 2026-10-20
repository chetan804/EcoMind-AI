"""Domain-level exceptions and the handlers that turn every failure into a structured error.

Error body (all non-2xx responses):
    {"error": {"code": "...", "message": "...", "details": [...] | null, "request_id": "..."}}
Stack traces, SQL and settings values are never included in a response.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, client-visible errors raised by services."""

    status_code = 500
    code = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class UnauthenticatedError(AppError):
    status_code = 401
    code = "unauthenticated"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class TooManyRequestsError(AppError):
    """429. Pass ``headers={"Retry-After": "<seconds>"}`` so clients know when to retry."""

    status_code = 429
    code = "rate_limited"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
}


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = {
        "error": {"code": code, "message": message, "details": details, "request_id": request_id}
    }
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(
            request, exc.status_code, exc.code, exc.message, exc.details, headers=exc.headers
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        headers = dict(exc.headers) if exc.headers else None
        return error_response(request, exc.status_code, code, str(exc.detail), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"location": [str(p) for p in err["loc"]], "message": err["msg"], "type": err["type"]}
            for err in exc.errors()
        ]
        return error_response(
            request, 422, "validation_error", "Request validation failed", details
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        return error_response(request, 500, "internal_error", "An unexpected error occurred")
