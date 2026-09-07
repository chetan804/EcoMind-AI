from app.models.complaint import Complaint, ComplaintStatusHistory


STATUS_TRANSITIONS = {
    "submitted": {"submitted", "under_review", "rejected"},
    "under_review": {"under_review", "assigned", "rejected"},
    "assigned": {"assigned", "in_progress", "rejected"},
    "in_progress": {"in_progress", "resolved", "rejected"},
    "resolved": {"resolved"},
    "rejected": {"rejected"},
}


def change_complaint_status(
    complaint: Complaint,
    new_status: str,
    changed_by: int,
    note: str | None = None,
) -> ComplaintStatusHistory:
    allowed_statuses = STATUS_TRANSITIONS.get(complaint.status, set())
    if new_status not in allowed_statuses:
        raise ValueError(
            f"Cannot change complaint status from "
            f"'{complaint.status}' to '{new_status}'"
        )

    history = ComplaintStatusHistory(
        complaint=complaint,
        changed_by=changed_by,
        old_status=complaint.status,
        new_status=new_status,
        note=note,
    )
    complaint.status = new_status
    return history
