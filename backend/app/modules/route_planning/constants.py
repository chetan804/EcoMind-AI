from __future__ import annotations

from enum import StrEnum


class RoutePlanStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
