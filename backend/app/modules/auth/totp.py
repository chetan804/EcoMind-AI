"""TOTP (RFC 6238) on top of HOTP (RFC 4226), standard library only.

Defaults match every mainstream authenticator app: HMAC-SHA1, 6 digits, 30 second steps. A code
is accepted for the current step and one step either side (clock drift). Each step can be
accepted once per factor: the caller stores the last accepted step (replay protection).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote, urlencode

PERIOD = 30
DIGITS = 6
DRIFT_STEPS = 1


def generate_secret() -> str:
    """160 random bits, base32 without padding (the format authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def hotp(secret: str, counter: int, digits: int = DIGITS) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def step_at(unix_time: float, period: int = PERIOD) -> int:
    return int(unix_time // period)


def totp(secret: str, unix_time: float, *, digits: int = DIGITS, period: int = PERIOD) -> str:
    return hotp(secret, step_at(unix_time, period), digits)


def match_step(
    secret: str,
    code: str,
    unix_time: float,
    *,
    last_used_step: int | None,
    digits: int = DIGITS,
    period: int = PERIOD,
) -> int | None:
    """Return the time step ``code`` is valid for, or ``None``.

    Steps at or before ``last_used_step`` are refused so a captured code cannot be replayed.
    Every candidate is compared in constant time.
    """
    if len(code) != digits or not (code.isascii() and code.isdigit()):
        return None
    now = step_at(unix_time, period)
    matched: int | None = None
    for step in range(now - DRIFT_STEPS, now + DRIFT_STEPS + 1):
        if hmac.compare_digest(hotp(secret, step, digits), code) and (
            last_used_step is None or step > last_used_step
        ):
            matched = step
    return matched


def provisioning_uri(secret: str, *, account: str, issuer: str) -> str:
    """``otpauth://`` URI that authenticator apps import (also rendered as a QR code)."""
    label = f"{quote(issuer)}:{quote(account)}"
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": PERIOD,
        }
    )
    return f"otpauth://totp/{label}?{query}"
