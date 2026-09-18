from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AIOperationLog(Base):
    __tablename__ = "ai_operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    operation = Column(String(80), nullable=False, index=True)
    model_name = Column(String(120), nullable=False)
    model_version = Column(String(50), nullable=False)
    provider = Column(String(80), nullable=False)
    input_type = Column(String(40), nullable=False)
    output_summary = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")
