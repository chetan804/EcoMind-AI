from sqlalchemy.orm import Session

from app.models.reward import RewardAccount, RewardActivity


POINT_RULES = {
    "report_submitted": 10,
    "collection_completed": 25,
}


def award_points(
    db: Session,
    user_id: int,
    activity_type: str,
    reference: str,
) -> RewardActivity | None:
    points = POINT_RULES.get(activity_type)
    if points is None:
        raise ValueError("Unsupported reward activity")

    existing = (
        db.query(RewardActivity)
        .filter(
            RewardActivity.user_id == user_id,
            RewardActivity.reference == reference,
        )
        .first()
    )
    if existing is not None:
        return None

    account = (
        db.query(RewardAccount)
        .filter(RewardAccount.user_id == user_id)
        .with_for_update()
        .first()
    )
    if account is None:
        account = RewardAccount(user_id=user_id, points=0)
        db.add(account)
        db.flush()

    account.points += points
    activity = RewardActivity(
        user_id=user_id,
        activity_type=activity_type,
        points=points,
        reference=reference,
    )
    db.add(activity)
    return activity
