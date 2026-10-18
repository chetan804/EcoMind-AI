"""Response schemas shared across modules: structured errors and operational status."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class LivenessResponse(BaseModel):
    status: Literal["ok"]


class DependencyStatus(BaseModel):
    status: Literal["ok", "failed"]
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, DependencyStatus]
