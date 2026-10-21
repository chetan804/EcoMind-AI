"""Request and response bodies of the administration API."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class UserAdminOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    mfa_enabled: bool
    email_verified: bool
    roles: list[str]
    created_at: dt.datetime
    last_login_at: dt.datetime | None


class RoleOut(BaseModel):
    name: str
    description: str | None
    is_system: bool
    user_count: int
    permissions: list[str]


class RolesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[str] = Field(min_length=1, max_length=10)
    reason: Reason


class ReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    occurred_at: dt.datetime
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    actor_email: str | None
    request_id: str | None
    ip_address: str | None
    changes: dict[str, Any] | None


class SystemInfo(BaseModel):
    """Non-secret runtime configuration. Secrets and filesystem paths are never included."""

    environment: str
    log_level: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    refresh_cookie_secure: bool
    refresh_cookie_samesite: str
    cors_allowed_origins: list[str]
    file_storage_backend: str
    max_upload_bytes: int
    reward_points_per_kg: int
    database_revision: str | None
    active_model_version: str | None
