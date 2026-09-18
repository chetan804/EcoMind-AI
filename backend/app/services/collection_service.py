from datetime import datetime, timezone

from app.models.collection import WasteCollection


STATUS_TRANSITIONS = {
    "assigned": {"assigned", "accepted", "in_progress", "cancelled"},
    "accepted": {"accepted", "in_progress", "cancelled"},
    "in_progress": {"in_progress", "arrived", "collected", "cancelled"},
    "arrived": {"arrived", "collected", "cancelled"},
    "collected": {"collected", "verified"},
    "verified": {"verified"},
    "cancelled": {"cancelled"},
}


def update_collection_status(
    collection: WasteCollection,
    new_status: str,
) -> None:
    allowed_statuses = STATUS_TRANSITIONS.get(collection.status, set())
    if new_status not in allowed_statuses:
        raise ValueError(
            f"Cannot change collection status from "
            f"'{collection.status}' to '{new_status}'"
        )

    collection.status = new_status
    if new_status == "collected" and collection.collected_at is None:
        collection.collected_at = datetime.now(timezone.utc)
