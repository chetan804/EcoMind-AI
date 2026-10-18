from __future__ import annotations

from enum import StrEnum


class PassportStatus(StrEnum):
    ACTIVE = "active"
    IN_PROCESSING = "in_processing"
    RECOVERED = "recovered"
    RETIRED = "retired"


class CustodyEventType(StrEnum):
    CREATED = "created"
    COLLECTED = "collected"
    TRANSFERRED = "transferred"
    RECEIVED = "received"
    PROCESSED = "processed"
    VERIFIED = "verified"
