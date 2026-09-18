from app.models.waste_report import WasteReport


STATUS_TRANSITIONS = {
    "draft": {"draft", "submitted", "cancelled"},
    "reported": {"reported", "submitted", "assigned", "rejected", "cancelled"},
    "submitted": {"submitted", "ai_analyzed", "verified", "rejected", "cancelled"},
    "ai_analyzed": {"ai_analyzed", "verified", "rejected", "cancelled"},
    "verified": {"verified", "assigned", "rejected", "cancelled"},
    "assigned": {"assigned", "scheduled", "cancelled"},
    "scheduled": {"scheduled", "in_progress", "cancelled"},
    "in_progress": {"in_progress", "collected", "cancelled"},
    "collected": {"collected", "verified_collection"},
    "verified_collection": {"verified_collection", "resolved"},
    "resolved": {"resolved"},
    "rejected": {"rejected"},
    "cancelled": {"cancelled"},
}


def update_report_status(report: WasteReport, new_status: str) -> None:
    allowed_statuses = STATUS_TRANSITIONS.get(report.status, set())
    if new_status not in allowed_statuses:
        raise ValueError(
            f"Cannot change report status from '{report.status}' to '{new_status}'"
        )

    report.status = new_status