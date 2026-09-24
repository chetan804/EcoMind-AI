"""Fleet: vehicles and driver profiles."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class VehicleType(str, enum.Enum):
    compactor_truck = "compactor_truck"
    tipper_truck = "tipper_truck"
    van = "van"
    ev_van = "ev_van"
    tricycle = "tricycle"
    loader = "loader"
    other = "other"


class FuelType(str, enum.Enum):
    diesel = "diesel"
    petrol = "petrol"
    cng = "cng"
    electric = "electric"
    hybrid = "hybrid"


class VehicleStatus(str, enum.Enum):
    active = "active"
    maintenance = "maintenance"
    retired = "retired"


class Vehicle(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "vehicles"

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120))
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("operational_units.id", ondelete="SET NULL")
    )
    vehicle_type: Mapped[VehicleType] = mapped_column(
        SAEnum(VehicleType, native_enum=False, length=32), default=VehicleType.compactor_truck, nullable=False
    )
    fuel_type: Mapped[FuelType] = mapped_column(
        SAEnum(FuelType, native_enum=False, length=16), default=FuelType.diesel, nullable=False
    )
    plate_number: Mapped[str | None] = mapped_column(String(32))
    capacity_kg: Mapped[float | None] = mapped_column(Numeric(12, 2))
    capacity_volume_m3: Mapped[float | None] = mapped_column(Numeric(10, 2))
    status: Mapped[VehicleStatus] = mapped_column(
        SAEnum(VehicleStatus, native_enum=False, length=16), default=VehicleStatus.active, nullable=False
    )
    odometer_km: Mapped[float | None] = mapped_column(Numeric(12, 1))
    depot_lat: Mapped[float | None] = mapped_column(Float)
    depot_lng: Mapped[float | None] = mapped_column(Float)
    current_lat: Mapped[float | None] = mapped_column(Float)
    current_lng: Mapped[float | None] = mapped_column(Float)
    current_route_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL", use_alter=True)
    )
    last_ping_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # True only when positions originate from the labelled simulator.
    position_is_simulated: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_vehicle_code"),)


class DriverProfile(UUIDMixin, TimestampMixin, TenantScoped, Base):
    """Operational profile for users acting as collectors/drivers."""

    __tablename__ = "driver_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    license_number: Mapped[str | None] = mapped_column(String(64))
    license_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    default_vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
