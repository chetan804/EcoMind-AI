from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class WasteReport(Base):
    __tablename__ = "waste_reports"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    waste_type = Column(
        String(50),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=False,
    )

    location = Column(
        String(255),
        nullable=False,
    )

    latitude = Column(Float, nullable=True)

    longitude = Column(Float, nullable=True)

    status = Column(
        String(30),
        nullable=False,
        default="reported",
    )

    ai_waste_type = Column(
        String(50),
        nullable=True,
    )

    ai_confidence = Column(
        Float,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User")

    collection = relationship(
        "WasteCollection",
        back_populates="report",
        uselist=False,
    )