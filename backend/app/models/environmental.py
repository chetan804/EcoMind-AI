from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class EnvironmentalSource(Base):
    __tablename__ = "environmental_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    source_type = Column(String(30), nullable=False, default="manual")
    location = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    readings = relationship("EnvironmentalReading", back_populates="source")


class EnvironmentalReading(Base):
    __tablename__ = "environmental_readings"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("environmental_sources.id"), nullable=False)
    metric = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source = relationship("EnvironmentalSource", back_populates="readings")


class SmartBin(Base):
    __tablename__ = "smart_bins"

    id = Column(Integer, primary_key=True, index=True)
    bin_code = Column(String(80), nullable=False, unique=True)
    location = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    fill_level = Column(Float, nullable=True)
    battery_level = Column(Float, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), nullable=False, default="registered")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
