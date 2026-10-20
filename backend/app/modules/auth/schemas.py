"""Request and response models for the auth endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(_Strict):
    email: EmailStr
    password: str = Field(max_length=1024)
    full_name: str = Field(min_length=1, max_length=200)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value


class LoginRequest(_Strict):
    # Plain str on purpose: a malformed address gets the same generic failure as a wrong one.
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class ChangePasswordRequest(_Strict):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(max_length=1024)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
    permissions: list[str]


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth token type label
    expires_in: int = Field(description="Access token lifetime in seconds")
    user: UserOut
