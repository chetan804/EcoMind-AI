"""Deterministic identifiers and random streams.

Every synthetic row gets a UUID that starts with the ASCII bytes ``SYNT`` (``53594e54-``). The rest
is a hash of (seed, kind, key), so the same inputs always give the same id, and a synthetic row can
be recognised (and a real row can never be mistaken for one) from its primary key alone.
"""

from __future__ import annotations

import hashlib
import random
import uuid

PREFIX = b"SYNT"
PREFIX_TEXT = "53594e54-"


def sid(seed: int, kind: str, *key: object) -> uuid.UUID:
    digest = hashlib.sha256(f"{seed}|{kind}|{'|'.join(map(str, key))}".encode()).digest()
    raw = bytearray(PREFIX + digest[:12])
    raw[6] = (raw[6] & 0x0F) | 0x80  # RFC 9562 version 8: application-defined
    raw[8] = (raw[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(raw))


def stream(seed: int, kind: str, *key: object) -> random.Random:
    """An independent random stream per entity, so changing one entity never shifts another."""
    digest = hashlib.sha256(f"rng|{seed}|{kind}|{'|'.join(map(str, key))}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def is_synthetic(value: object) -> bool:
    return str(value).startswith(PREFIX_TEXT)
