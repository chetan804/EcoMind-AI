from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import RoleID
from app.core.security import get_current_user, require_role
from app.db.database import get_db
from app.models.carbon import CarbonCredit, CarbonTransaction
from app.models.user import User
from app.schemas.carbon import (
    CarbonCreditResponse,
    CarbonEarnRequest,
    CarbonPurchaseRequest,
    CarbonTransactionResponse,
)
from app.services.carbon_service import get_balance, purchase_credit


router = APIRouter(prefix="/carbon", tags=["Carbon Credits"])


@router.get("/balance", response_model=Decimal)
def get_my_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_balance(db, current_user.id)


@router.get("/marketplace", response_model=list[CarbonCreditResponse])
def get_marketplace(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(CarbonCredit)
        .filter(
            CarbonCredit.owner_id != current_user.id,
            CarbonCredit.status == "available",
            CarbonCredit.amount > 0,
        )
        .order_by(CarbonCredit.created_at.asc())
        .all()
    )


@router.post(
    "/buy/{credit_id}",
    response_model=CarbonTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def buy_credit(
    credit_id: int,
    purchase_data: CarbonPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    transaction = purchase_credit(
        db,
        current_user.id,
        credit_id,
        Decimal(purchase_data.amount),
    )
    db.commit()
    db.refresh(transaction)
    return transaction


@router.post(
    "/admin/earn",
    response_model=CarbonCreditResponse,
    status_code=status.HTTP_201_CREATED,
)
def earn_credit(
    earn_data: CarbonEarnRequest,
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.id == earn_data.user_id, User.is_active.is_(True))
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    credit = CarbonCredit(
        owner_id=user.id,
        amount=earn_data.amount,
        source=earn_data.source,
        status="available",
    )
    db.add(credit)
    db.add(
        CarbonTransaction(
            buyer_id=user.id,
            credit=credit,
            amount=earn_data.amount,
            transaction_type="earned",
            status="completed",
        )
    )
    db.commit()
    db.refresh(credit)
    return credit


@router.get("/transactions", response_model=list[CarbonTransactionResponse])
def get_my_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(CarbonTransaction)
        .filter(
            (CarbonTransaction.buyer_id == current_user.id)
            | (CarbonTransaction.seller_id == current_user.id)
        )
        .order_by(CarbonTransaction.created_at.desc())
        .all()
    )
