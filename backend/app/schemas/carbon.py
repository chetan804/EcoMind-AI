from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CarbonCreditResponse(BaseModel):
    id: int
    owner_id: int
    amount: Decimal
    source: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CarbonEarnRequest(BaseModel):
    user_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    source: str = Field(min_length=2, max_length=100)


class CarbonPurchaseRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class CarbonTransactionResponse(BaseModel):
    id: int
    buyer_id: int | None
    seller_id: int | None
    credit_id: int
    amount: Decimal
    transaction_type: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
