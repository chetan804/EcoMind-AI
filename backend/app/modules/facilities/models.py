"""Facilities, processing centers and depots. Owned by the ``facilities`` module."""

from __future__ import annotations

import decimal

from sqlalchemy import CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    GeoPointMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
    geo_point_constraints,
)
from app.modules.facilities.constants import FacilityStatus, FacilityType


class Facility(UUIDPrimaryKeyMixin, TimestampMixin, GeoPointMixin, Base):
    __tablename__ = "facilities"
    __table_args__ = (
        CheckConstraint(
            "daily_capacity_kg IS NULL OR daily_capacity_kg > 0", name="capacity_positive"
        ),
        *geo_point_constraints(),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_type: Mapped[FacilityType] = mapped_column(
        enum_column(FacilityType), nullable=False, index=True
    )
    status: Mapped[FacilityStatus] = mapped_column(
        enum_column(FacilityStatus),
        nullable=False,
        server_default=FacilityStatus.ACTIVE.value,
    )
    address_line: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str | None] = mapped_column(String(2))
    daily_capacity_kg: Mapped[decimal.Decimal | None] = mapped_column(Numeric(14, 3))
    contact_email: Mapped[str | None] = mapped_column(String(320))
