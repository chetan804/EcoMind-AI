from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.carbon import CarbonCredit, CarbonTransaction


def get_balance(db: Session, user_id: int) -> Decimal:
    balance = (
        db.query(func.coalesce(func.sum(CarbonCredit.amount), 0))
        .filter(
            CarbonCredit.owner_id == user_id,
            CarbonCredit.status == "available",
        )
        .scalar()
    )
    return Decimal(balance)


def purchase_credit(
    db: Session,
    buyer_id: int,
    credit_id: int,
    amount: Decimal,
) -> CarbonTransaction:
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive")

    credit = (
        db.query(CarbonCredit)
        .filter(
            CarbonCredit.id == credit_id,
            CarbonCredit.status == "available",
        )
        .with_for_update()
        .first()
    )
    if credit is None:
        raise HTTPException(status_code=404, detail="Carbon credit not found")
    if credit.owner_id == buyer_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot purchase your own credits",
        )
    if Decimal(credit.amount) < amount:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insufficient credit availability",
        )

    credit.amount = Decimal(credit.amount) - amount
    if credit.amount == 0:
        credit.status = "exhausted"

    purchased_credit = CarbonCredit(
        owner_id=buyer_id,
        amount=amount,
        source="purchased",
        status="available",
    )
    transaction = CarbonTransaction(
        buyer_id=buyer_id,
        seller_id=credit.owner_id,
        credit_id=credit.id,
        amount=amount,
        transaction_type="purchased",
        status="completed",
    )
    db.add_all([purchased_credit, transaction])
    return transaction
