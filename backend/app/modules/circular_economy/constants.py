from __future__ import annotations

from enum import StrEnum


class RecoveryMethod(StrEnum):
    RECYCLED = "recycled"
    COMPOSTED = "composted"
    REUSED = "reused"
    REFURBISHED = "refurbished"
    ENERGY_RECOVERED = "energy_recovered"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
