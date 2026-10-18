from __future__ import annotations

from enum import StrEnum


class WasteReportStatus(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    CLOSED = "closed"
