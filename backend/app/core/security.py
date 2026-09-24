"""Password hashing and token utilities.

- Passwords: Argon2id (argon2-cffi) with per-hash random salt.
- Access tokens: short-lived JWT (HS256) carrying the user id + platform flag.
  The JWT authenticates the *user*, never the *organization*: organization
  context is resolved per-request from the active membership so tokens stay
  valid when the user switches or is removed from an organization.
- Refresh tokens: opaque 256-bit secrets stored only as SHA-256 hashes,
  rotated on every use; compromise of the store does not yield usable tokens.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings
from app.core.errors import AuthError

_password_hasher = PasswordHasher()  # argon2id, 64 MiB, t=3


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


# --- Access tokens ---------------------------------------------------------


def create_access_token(user_id: uuid.UUID, is_platform_admin: bool = False) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "pa": is_platform_admin,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "jti": secrets.token_hex(8),
        "typ": "access",
    }
    return jwt.encode(payload, settings.effective_secret_key(), algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.effective_secret_key(), algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Access token expired.") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("Invalid access token.") from e
    if payload.get("typ") != "access":
        raise AuthError("Invalid token type.")
    return payload


# --- Opaque secrets (refresh tokens, device keys, invite tokens) ------------


def new_opaque_token(prefix: str = "emr") -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    """SHA-256 for at-rest storage of opaque high-entropy tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def token_fingerprint(token: str) -> str:
    """Non-reversible display prefix for UIs and logs."""
    return token[:8] + "…"


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b)
