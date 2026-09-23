"""Sustainability: versioned emission factors and auditable carbon records.

Factor provenance is first-class: source, region, year, unit, methodology and
version are stored on every factor, and every computed carbon record retains
the factor version and assumptions it was derived from. Metrics are labelled
measured / estimated / modeled — never presented as more certain than they are.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class FactorCategory(str, enum.Enum):
    fuel = "fuel"
    electricity = "electricity"
    waste_treatment = "waste_treatment"
    other = "other"


class DataQuality(str, enum.Enum):
    measured = "measured"
    estimated = "estimated"
    modeled = "modeled"


class EmissionScope(str, enum.Enum):
    scope1 = "scope1"
    scope2 = "scope2"
    scope3 = "scope3"
    avoided = "avoided"  # comparative/baseline framing, documented per methodology


class EmissionFactor(UUIDMixin, TimestampMixin, Base):
    """Platform-level versioned factor library (not tenant-scoped)."""

    __tablename__ = "emission_factors"

    code: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[FactorCategory] = mapped_column(
        SAEnum(FactorCategory, native_enum=False, length=32), nullable=False
    )
    source: Mapped[str] = mapped_column(String(120), nullable=False)  # e.g. "EPA GHG Emission Factors Hub 2024"
    source_url: Mapped[str | None] = mapped_column(String(500))
    region: Mapped[str] = mapped_column(String(64), default="global", nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "kg_co2e_per_litre"
    value: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False)
    methodology: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(16), default="1", nullable=False)
    uncertainty_pct: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (UniqueConstraint("code", "version", name="uq_emission_factor_code_version"),)


class CarbonRecord(UUIDMixin, TimestampMixin, TenantScoped, Base):
    """One computed emissions/avoidance line item for an org and period."""

    __tablename__ = "carbon_records"

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    scope: Mapped[EmissionScope] = mapped_column(
        SAEnum(EmissionScope, native_enum=False, length=16), nullable=False
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)  # fleet_fuel, landfill, recycling...
    activity_value: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    activity_unit: Mapped[str] = mapped_column(String(48), nullable=False)
    factor_code: Mapped[str | None] = mapped_column(String(96))
    factor_version: Mapped[str | None] = mapped_column(String(16))
    co2e_kg: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    quality: Mapped[DataQuality] = mapped_column(
        SAEnum(DataQuality, native_enum=False, length=16), nullable=False
    )
    methodology: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_carbon_records_org_period", "organization_id", "period_start"),)


class WasteTreatment(UUIDMixin, TimestampMixin, TenantScoped, Base):
    """Where collected waste actually goes — the activity data for diversion.

    Records are derived from completed collection events when available
    (measured), or entered manually with an explicit estimated flag.
    """

    __tablename__ = "waste_treatments"

    treatment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    waste_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("waste_categories.id", ondelete="SET NULL")
    )
    # landfill | recycling | composting | incineration | ad (anaerobic digestion) | other
    destination: Mapped[str] = mapped_column(String(48), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    quality: Mapped[DataQuality] = mapped_column(
        SAEnum(DataQuality, native_enum=False, length=16), default=DataQuality.estimated, nullable=False
    )
    source_event_id: Mapped[uuid.UUID | None] = mapped_column()  # collection_event provenance
    notes: Mapped[str | None] = mapped_column(Text)
