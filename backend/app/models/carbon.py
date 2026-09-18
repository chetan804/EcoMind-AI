from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class CarbonCredit(Base):
    __tablename__ = "carbon_credits"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 3), nullable=False)
    source = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False, default="available")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owner = relationship("User")


class CarbonTransaction(Base):
    __tablename__ = "carbon_transactions"

    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    credit_id = Column(Integer, ForeignKey("carbon_credits.id"), nullable=False)
    amount = Column(Numeric(12, 3), nullable=False)
    transaction_type = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    buyer = relationship("User", foreign_keys=[buyer_id])
    seller = relationship("User", foreign_keys=[seller_id])
    credit = relationship("CarbonCredit")
