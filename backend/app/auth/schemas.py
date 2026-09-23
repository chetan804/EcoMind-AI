"""Auth API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    # Optional: join an open organization as a citizen at signup.
    join_org_slug: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str | None = None
    is_active: bool
    email_verified_at: datetime | None = None
    locale: str
    created_at: datetime


class MembershipPublic(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    role_code: str
    role_name: str
    is_default: bool
    is_demo: bool
    permissions: list[str]


class MeOut(UserPublic):
    is_platform_admin: bool
    memberships: list[MembershipPublic]


class AuthResponse(BaseModel):
    tokens: TokenPair
    user: MeOut


class MessageOut(BaseModel):
    message: str
