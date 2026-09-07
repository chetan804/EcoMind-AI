from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class RewardAccount(Base):
    __tablename__ = "reward_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    points = Column(Integer, nullable=False, default=0, server_default="0")

    user = relationship("User")


class RewardActivity(Base):
    __tablename__ = "reward_activities"
    __table_args__ = (
        UniqueConstraint("user_id", "reference", name="uq_reward_activity_reference"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity_type = Column(String(50), nullable=False)
    points = Column(Integer, nullable=False)
    reference = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")
