from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.reward import RewardAccount, RewardActivity
from app.models.user import User
from app.schemas.reward import RewardAccountResponse, RewardActivityResponse


router = APIRouter(prefix="/rewards", tags=["Rewards"])


@router.get("/me", response_model=RewardAccountResponse)
def get_my_rewards(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = (
        db.query(RewardAccount)
        .filter(RewardAccount.user_id == current_user.id)
        .first()
    )
    if account is None:
        return RewardAccountResponse(user_id=current_user.id, points=0)
    return account


@router.get("/activities", response_model=list[RewardActivityResponse])
def get_my_reward_activities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(RewardActivity)
        .filter(RewardActivity.user_id == current_user.id)
        .order_by(RewardActivity.created_at.desc())
        .all()
    )
