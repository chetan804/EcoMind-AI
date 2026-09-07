from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RewardAccountResponse(BaseModel):
    user_id: int
    points: int

    model_config = ConfigDict(from_attributes=True)


class RewardActivityResponse(BaseModel):
    id: int
    activity_type: str
    points: int
    reference: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
