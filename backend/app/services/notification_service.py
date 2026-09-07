from app.models.notification import Notification


def create_notification(
    user_id: int,
    event_type: str,
    title: str,
    message: str,
) -> Notification:
    return Notification(
        user_id=user_id,
        event_type=event_type,
        title=title,
        message=message,
    )
