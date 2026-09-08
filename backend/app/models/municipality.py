from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Municipality(Base):
    __tablename__ = "municipalities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(30), unique=True, nullable=False, index=True)
    region = Column(String(120), nullable=False)
    external_id = Column(String(80), unique=True, nullable=True, index=True)
    contact_email = Column(String(150), nullable=True)
    phone = Column(String(40), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    service_areas = relationship(
        "ServiceArea",
        back_populates="municipality",
        cascade="all, delete-orphan",
    )
    sync_logs = relationship(
        "MunicipalSyncLog",
        back_populates="municipality",
        cascade="all, delete-orphan",
    )


class ServiceArea(Base):
    __tablename__ = "service_areas"

    id = Column(Integer, primary_key=True, index=True)
    municipality_id = Column(Integer, ForeignKey("municipalities.id"), nullable=False)
    name = Column(String(150), nullable=False)
    code = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="active")
    external_id = Column(String(80), nullable=True, index=True)
    boundary_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    municipality = relationship("Municipality", back_populates="service_areas")

    __table_args__ = (
        UniqueConstraint("municipality_id", "code", name="uq_service_area_municipality_code"),
    )


class MunicipalSyncLog(Base):
    __tablename__ = "municipal_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    municipality_id = Column(Integer, ForeignKey("municipalities.id"), nullable=False)
    sync_type = Column(String(60), nullable=False)
    provider = Column(String(60), nullable=False, default="internal")
    status = Column(String(30), nullable=False, default="queued")
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    municipality = relationship("Municipality", back_populates="sync_logs")
