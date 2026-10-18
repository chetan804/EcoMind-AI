from __future__ import annotations

from enum import StrEnum


class NotificationCategory(StrEnum):
    COLLECTION = "collection"
    REPORT = "report"
    INCIDENT = "incident"
    ANOMALY = "anomaly"
    REWARD = "reward"
    SYSTEM = "system"
