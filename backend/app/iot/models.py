"""IoT: devices, telemetry, alert rules and raised alerts.

Device authentication uses per-device API keys (stored hashed). A device key
never establishes tenant identity by itself: the device row's organization
binding is authoritative, and ingestion re-validates the key on every call.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    func,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class DeviceKind(str, enum.Enum):
    smart_bin = "smart_bin"
    fill_sensor = "fill_sensor"
    environmental_sensor = "environmental_sensor"
    gps_tracker = "gps_tracker"
    other = "other"


class DeviceStatus(str, enum.Enum):
    registered = "registered"
    active = "active"
    suspended = "suspended"
    revoked = "revoked"


class TelemetrySource(str, enum.Enum):
    device = "device"
    simulator = "simulator"
    manual = "manual"


class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    high = "high"
    critical = "critical"


class AlertRuleMetric(str, enum.Enum):
    fill_pct = "fill_pct"
    temperature_c = "temperature_c"
    battery_pct = "battery_pct"
    offline_hours = "offline_hours"


class AlertStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class Device(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "devices"

    device_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[DeviceKind] = mapped_column(
        SAEnum(DeviceKind, native_enum=False, length=32), default=DeviceKind.fill_sensor, nullable=False
    )
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[DeviceStatus] = mapped_column(
        SAEnum(DeviceStatus, native_enum=False, length=16), default=DeviceStatus.registered, nullable=False
    )
    collection_point_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("collection_points.id", ondelete="SET NULL")
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    firmware: Mapped[str | None] = mapped_column(String(64))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    # Live snapshot (denormalised from telemetry for cheap reads)
    current_fill_pct: Mapped[float | None] = mapped_column(Float)
    current_temperature_c: Mapped[float | None] = mapped_column(Float)
    current_battery_pct: Mapped[float | None] = mapped_column(Float)
    last_telemetry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Simulator origin is flagged at the row level — never silently mixed.
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class TelemetryReading(Base):
    __tablename__ = "telemetry_readings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    fill_pct: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    battery_pct: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    signal_strength_dbm: Mapped[float | None] = mapped_column(Float)
    source: Mapped[TelemetrySource] = mapped_column(
        SAEnum(TelemetrySource, native_enum=False, length=16), default=TelemetrySource.device, nullable=False
    )
    payload: Mapped[dict | None] = mapped_column(JSON)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_telemetry_device_recorded", "device_id", "recorded_at"),
        Index("ix_telemetry_org_recorded", "organization_id", "recorded_at"),
    )


class AlertRule(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "alert_rules"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    metric: Mapped[AlertRuleMetric] = mapped_column(
        SAEnum(AlertRuleMetric, native_enum=False, length=32), nullable=False
    )
    operator: Mapped[str] = mapped_column(String(4), nullable=False)  # gt | gte | lt | lte
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity, native_enum=False, length=16), default=AlertSeverity.warning, nullable=False
    )
    device_kind: Mapped[DeviceKind | None] = mapped_column(
        SAEnum(DeviceKind, native_enum=False, length=32)
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Alert(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "alerts"

    rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alert_rules.id", ondelete="SET NULL"))
    device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    route_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("routes.id", ondelete="SET NULL"))
    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity, native_enum=False, length=16), default=AlertSeverity.warning, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus, native_enum=False, length=16), default=AlertStatus.open, nullable=False, index=True
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_alerts_org_status", "organization_id", "status"),
        UniqueConstraint("rule_id", "device_id", "triggered_at", name="uq_alert_dedup"),
    )
