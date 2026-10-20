from __future__ import annotations

from enum import StrEnum


class WasteReportStatus(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    CLOSED = "closed"


# Review workflow. A report only moves along these edges; anything else is a 409.
# ``rejected`` and ``verified`` can be closed (archived); ``closed`` is terminal.
ALLOWED_TRANSITIONS: dict[WasteReportStatus, frozenset[WasteReportStatus]] = {
    WasteReportStatus.SUBMITTED: frozenset(
        {WasteReportStatus.UNDER_REVIEW, WasteReportStatus.VERIFIED, WasteReportStatus.REJECTED}
    ),
    WasteReportStatus.UNDER_REVIEW: frozenset(
        {WasteReportStatus.VERIFIED, WasteReportStatus.REJECTED}
    ),
    WasteReportStatus.VERIFIED: frozenset({WasteReportStatus.CLOSED}),
    WasteReportStatus.REJECTED: frozenset({WasteReportStatus.CLOSED}),
    WasteReportStatus.CLOSED: frozenset(),
}

# Upload limits that are not deployment settings (the byte limit is ``MAX_UPLOAD_BYTES``).
MAX_ATTACHMENTS_PER_REPORT = 5
MAX_UNATTACHED_UPLOADS_PER_USER = 20
MAX_IMAGE_PIXELS = 40_000_000  # decoded size cap (decompression-bomb guard)
MIN_IMAGE_SIDE_PX = 32
