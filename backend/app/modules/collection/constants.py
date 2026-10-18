from __future__ import annotations

from enum import StrEnum


class CollectionTaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class CollectionEventType(StrEnum):
    ARRIVED = "arrived"
    COLLECTED = "collected"
    SKIPPED = "skipped"
    CONTAMINATED = "contaminated"
    DELIVERED_TO_FACILITY = "delivered_to_facility"
