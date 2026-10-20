"""Symmetric encryption and keyed hashing derived from ``SECRET_KEY``.

Used for secrets that must be recoverable (a TOTP shared secret) and for low-entropy-free tokens
that must only be comparable (recovery codes). Keys are derived per purpose with HKDF-SHA256, so
the JWT signing key is never used directly as an encryption key.

Rotating ``SECRET_KEY`` makes previously encrypted values undecryptable: affected users must
re-enrol their authenticator. This is documented in docs/security/mfa.md.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_MFA_SECRET_INFO = b"ecomind-ai/mfa-secret/v1"


class DecryptionError(Exception):
    """The ciphertext is corrupt, or was encrypted under a different ``SECRET_KEY``."""


def _fernet(secret_key: str, info: bytes) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(
        secret_key.encode("utf-8")
    )
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_mfa_secret(secret_key: str, plaintext: str) -> str:
    return _fernet(secret_key, _MFA_SECRET_INFO).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_mfa_secret(secret_key: str, ciphertext: str) -> str:
    try:
        return _fernet(secret_key, _MFA_SECRET_INFO).decrypt(ciphertext.encode("ascii")).decode()
    except (InvalidToken, ValueError) as exc:
        raise DecryptionError("Cannot decrypt the stored value") from exc


def keyed_hash(secret_key: str, purpose: str, value: str) -> str:
    """HMAC-SHA256 hex digest of ``value`` under a key derived for ``purpose``."""
    key = hashlib.sha256(f"{purpose}:".encode() + secret_key.encode("utf-8")).digest()
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()
