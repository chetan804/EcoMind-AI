"""Fleet vehicles and availability. Owned by the ``fleet`` module."""

from __future__ import annotations

import decimal
import uuid

from sqlalchemy import CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column, fk_uuid
from app.modules.fleet.constants import VehicleStatus, VehicleType


class FleetVehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fleet_vehicles"
    __table_args__ = (CheckConstraint("capacity_kg > 0", name="capacity_positive"),)

    registration_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(enum_column(VehicleType), nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(
        enum_column(VehicleStatus),
        nullable=False,
        index=True,
        server_default=VehicleStatus.AVAILABLE.value,
    )
    capacity_kg: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    home_facility_id: Mapped[uuid.UUID | None] = fk_uuid("facilities.id", nullable=True)
