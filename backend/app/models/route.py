from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class CollectionRoute(Base):
    __tablename__ = "collection_routes"

    id = Column(Integer, primary_key=True, index=True)
    collector_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(30), nullable=False, default="generated")
    estimated_distance_km = Column(Float, nullable=False, default=0)
    estimated_duration_minutes = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    collector = relationship("User", foreign_keys=[collector_id])
    stops = relationship(
        "RouteStop",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStop.stop_order",
    )


class RouteStop(Base):
    __tablename__ = "route_stops"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("collection_routes.id"), nullable=False)
    collection_id = Column(
        Integer,
        ForeignKey("waste_collections.id"),
        nullable=False,
        unique=True,
    )
    stop_order = Column(Integer, nullable=False)
    distance_from_previous_km = Column(Float, nullable=False, default=0)

    route = relationship("CollectionRoute", back_populates="stops")
    collection = relationship("WasteCollection")
