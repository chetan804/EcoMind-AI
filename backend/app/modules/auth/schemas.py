"""Request and response models for the auth endpoints."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

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


class MfaStatusOut(BaseModel):
    enabled: bool
    pending_enrollment: bool = Field(description="A secret was issued but not yet confirmed")
    enabled_at: dt.datetime | None
    recovery_codes_remaining: int


class MfaEnrollOut(BaseModel):
    """Shown once. The secret is not returned again after enrolment is confirmed."""

    secret: str = Field(description="Base32 shared secret for manual entry")
    otpauth_uri: str = Field(description="URI for authenticator apps and QR codes")
    issuer: str
    algorithm: str = "SHA1"
    digits: int
    period_seconds: int


class MfaCodeRequest(_Strict):
    code: str = Field(min_length=6, max_length=20, description="6-digit code")


class MfaProofRequest(_Strict):
    """Disabling or re-issuing recovery codes needs the password *and* a current code."""

    password: str = Field(min_length=1, max_length=1024)
    code: str = Field(min_length=6, max_length=20, description="6-digit code or a recovery code")


class MfaRecoveryCodesOut(BaseModel):
    recovery_codes: list[str] = Field(description="Shown once; each works one time")


class MfaChallenge(BaseModel):
    """Login response for accounts with MFA: no access token until the second step."""

    mfa_required: Literal[True] = True
    mfa_token: str = Field(description="Send to POST /auth/mfa/verify with a code")
    expires_in: int = Field(description="Seconds the challenge stays valid")


class MfaVerifyRequest(_Strict):
    mfa_token: str = Field(min_length=10, max_length=2048)
    code: str = Field(min_length=6, max_length=20, description="6-digit code or a recovery code")
