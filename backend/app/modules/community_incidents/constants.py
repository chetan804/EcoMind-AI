from __future__ import annotations

from enum import StrEnum


class IncidentType(StrEnum):
    ILLEGAL_DUMPING = "illegal_dumping"
    OVERFLOWING_BIN = "overflowing_bin"
    HAZARDOUS_WASTE = "hazardous_waste"
    MISSED_COLLECTION = "missed_collection"
    OPEN_BURNING = "open_burning"
    OTHER = "other"


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
