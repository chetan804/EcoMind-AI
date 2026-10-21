"""Password hashing and token primitives.

Strategy (documented in docs/security/security-baseline.md):
- Passwords: Argon2id via argon2-cffi, with transparent rehash on login when parameters change.
- Access token: short-lived signed JWT (HS256) sent as ``Authorization: Bearer``; stateless.
- Refresh token: opaque random value held in an HttpOnly cookie; only its SHA-256 digest is stored
  server-side (``auth_sessions``), so it can be rotated and revoked.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.common.time import utc_now
from app.core.exceptions import UnauthenticatedError

ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - token type label, not a secret
MFA_CHALLENGE_TOKEN_TYPE = "mfa_challenge"  # noqa: S105 - token type label, not a secret
_ISSUER = "ecomind-ai"
# Cookie-authenticated endpoints (refresh, logout) require this request header. A cross-site page
# cannot add a custom header without a CORS preflight, which only configured origins pass.
CSRF_HEADER = "X-CSRF-Protection"
CSRF_HEADER_VALUE = "1"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(
    *,
    subject: uuid.UUID | str,
    secret_key: str,
    expires_in: timedelta,
    algorithm: str = "HS256",
    now: datetime | None = None,
) -> str:
    issued_at = now or utc_now()
    claims: dict[str, Any] = {
        "sub": str(subject),
        "type": ACCESS_TOKEN_TYPE,
        "iss": _ISSUER,
        "iat": issued_at,
        "exp": issued_at + expires_in,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, secret_key, algorithm=algorithm)


def decode_access_token(token: str, *, secret_key: str, algorithm: str = "HS256") -> dict[str, Any]:
    """Validate signature, expiry, issuer and token type. Raises ``UnauthenticatedError``."""
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],  # explicit allow-list: "none" and other algorithms are rejected
            issuer=_ISSUER,
            options={"require": ["sub", "exp", "iat", "iss", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("Invalid or expired credentials") from exc
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthenticatedError("Invalid or expired credentials")
    return claims


def create_mfa_challenge_token(
    *,
    subject: uuid.UUID | str,
    secret_key: str,
    expires_in: timedelta,
    algorithm: str = "HS256",
    now: datetime | None = None,
) -> str:
    """Short-lived proof that the password step succeeded. It grants no API access: the access
    token decoder rejects it because its ``type`` differs."""
    issued_at = now or utc_now()
    claims: dict[str, Any] = {
        "sub": str(subject),
        "type": MFA_CHALLENGE_TOKEN_TYPE,
        "iss": _ISSUER,
        "iat": issued_at,
        "exp": issued_at + expires_in,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, secret_key, algorithm=algorithm)


def decode_mfa_challenge_token(
    token: str, *, secret_key: str, algorithm: str = "HS256"
) -> dict[str, Any]:
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            issuer=_ISSUER,
            options={"require": ["sub", "exp", "iat", "iss", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("Invalid or expired credentials") from exc
    if claims.get("type") != MFA_CHALLENGE_TOKEN_TYPE:
        raise UnauthenticatedError("Invalid or expired credentials")
    return claims


def generate_refresh_token() -> str:
    """Return a new opaque refresh token (256 bits of randomness)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Digest stored in the database; the raw token is never persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_one_time_token() -> str:
    """A new single-use link token (256 bits of randomness), for e-mailed links."""
    return secrets.token_urlsafe(32)


def hash_one_time_token(token: str) -> str:
    """Digest stored in the database; the raw token exists only in the e-mailed link."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
