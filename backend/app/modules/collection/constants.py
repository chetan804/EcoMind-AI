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


# Lifecycle. A task only moves along these edges; anything else is a 409.
# ``assigned -> assigned`` is a re-assignment (the old assignment is ended, a history row is
# written). ``failed -> pending`` is "reschedule": a failed attempt can be tried again.
# ``completed`` and ``cancelled`` are terminal.
ALLOWED_TRANSITIONS: dict[CollectionTaskStatus, frozenset[CollectionTaskStatus]] = {
    CollectionTaskStatus.PENDING: frozenset(
        {CollectionTaskStatus.ASSIGNED, CollectionTaskStatus.CANCELLED}
    ),
    CollectionTaskStatus.ASSIGNED: frozenset(
        {
            CollectionTaskStatus.ASSIGNED,
            CollectionTaskStatus.IN_PROGRESS,
            CollectionTaskStatus.FAILED,
            CollectionTaskStatus.CANCELLED,
        }
    ),
    CollectionTaskStatus.IN_PROGRESS: frozenset(
        {
            CollectionTaskStatus.COMPLETED,
            CollectionTaskStatus.FAILED,
            CollectionTaskStatus.CANCELLED,
        }
    ),
    CollectionTaskStatus.FAILED: frozenset({CollectionTaskStatus.PENDING}),
    CollectionTaskStatus.COMPLETED: frozenset(),
    CollectionTaskStatus.CANCELLED: frozenset(),
}
OPEN_STATUSES = frozenset(
    {
        CollectionTaskStatus.PENDING,
        CollectionTaskStatus.ASSIGNED,
        CollectionTaskStatus.IN_PROGRESS,
    }
)
# Event types a collector may log by hand. ``collected`` is written only by ``/complete``
# (it carries the authoritative weight) and is rejected here.
MANUAL_EVENT_TYPES = frozenset(
    {
        CollectionEventType.ARRIVED,
        CollectionEventType.SKIPPED,
        CollectionEventType.CONTAMINATED,
        CollectionEventType.DELIVERED_TO_FACILITY,
    }
)
