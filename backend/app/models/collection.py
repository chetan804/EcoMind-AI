from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base


class WasteCollection(Base):
    __tablename__ = "waste_collections"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    report_id = Column(
        Integer,
        ForeignKey("waste_reports.id"),
        nullable=False,
        unique=True,
    )

    collector_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="assigned",
    )

    scheduled_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    collected_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    report = relationship(
        "WasteReport",
        back_populates="collection",
    )

    collector = relationship(
        "User",
        foreign_keys=[collector_id],
    )