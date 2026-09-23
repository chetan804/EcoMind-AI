"""IoT service: device lifecycle, telemetry ingestion, alert evaluation.

Device authentication: per-device API keys (stored SHA-256). The key lookup
resolves the device and its organization binding — a device ID alone never
establishes tenant identity. Payloads are strictly validated; readings are
immutable rows; the device's live snapshot is updated transactionally.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select, update

from app.core.db import AsyncSession, utcnow
from app.core.errors import AuthError, NotFoundError, ValidationApiError
from app.core.logging import get_logger
from app.core.security import hash_token, new_opaque_token
from app.iot.models import (
    Alert,
    AlertRule,
    AlertSeverity,
    Device,
    DeviceStatus,
    TelemetryReading,
    TelemetrySource,
)
from app.notifications.service import notify_role

log = get_logger("iot")

OP = {
    "gt": lambda v, t: v > t,
    "gte": lambda v, t: v >= t,
    "lt": lambda v, t: v < t,
    "lte": lambda v, t: v <= t,
}


async def authenticate_device(session: AsyncSession, *, device_key: str, api_key: str) -> Device:
    """Resolve device by public key + verify API key (constant-time compare)."""
    import hashlib
    import hmac

    device = (
        await session.execute(select(Device).where(Device.device_key == device_key))
    ).scalar_one_or_none()
    if device is None:
        raise AuthError("Unknown device.")
    candidate = hashlib.sha256(api_key.encode()).hexdigest()
    if not hmac.compare_digest(candidate, device.api_key_hash):
        raise AuthError("Invalid device credentials.")
    if device.status != DeviceStatus.active:
        raise AuthError(f"Device is {device.status.value}.")
    return device


async def register_device(
    session: AsyncSession, *, organization_id: uuid.UUID, name: str, device_key: str | None,
    kind: str, collection_point_id: uuid.UUID | None, zone_id: uuid.UUID | None,
    latitude: float | None, longitude: float | None, is_simulated: bool = False,
) -> tuple[Device, str]:
    key = device_key or f"BIN-{uuid.uuid4().hex[:10].upper()}"
    dupe = (
        await session.execute(select(Device).where(Device.device_key == key))
    ).scalar_one_or_none()
    if dupe:
        raise ValidationApiError("device_key already exists.")
    from app.iot.models import DeviceKind

    try:
        device_kind = DeviceKind(kind)
    except ValueError as e:
        raise ValidationApiError(f"Unknown device kind '{kind}'.") from e
    api_key = new_opaque_token("emd")
    device = Device(
        organization_id=organization_id,
        device_key=key,
        name=name,
        kind=device_kind,
        api_key_hash=hash_token(api_key),
        api_key_prefix=api_key[:8],
        status=DeviceStatus.active,
        collection_point_id=collection_point_id,
        zone_id=zone_id,
        latitude=latitude,
        longitude=longitude,
        is_simulated=is_simulated,
    )
    session.add(device)
    await session.flush()
    return device, api_key


async def rotate_device_key(session: AsyncSession, *, organization_id: uuid.UUID, device_id: uuid.UUID) -> tuple[Device, str]:
    device = await get_device(session, organization_id, device_id)
    api_key = new_opaque_token("emd")
    device.api_key_hash = hash_token(api_key)
    device.api_key_prefix = api_key[:8]
    return device, api_key


async def get_device(session: AsyncSession, organization_id: uuid.UUID, device_id: uuid.UUID) -> Device:
    d = (
        await session.execute(
            select(Device).where(Device.id == device_id, Device.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if d is None:
        raise NotFoundError("Device not found.")
    return d


async def ingest_telemetry(
    session: AsyncSession,
    *,
    device: Device,
    recorded_at,
    fill_pct: float | None,
    temperature_c: float | None,
    battery_pct: float | None,
    weight_kg: float | None,
    signal_strength_dbm: float | None,
    source: TelemetrySource = TelemetrySource.device,
    payload: dict | None = None,
) -> TelemetryReading:
    """Validate, persist, update snapshot, evaluate alerts."""
    for name, value, lo, hi in (
        ("fill_pct", fill_pct, 0.0, 100.0),
        ("battery_pct", battery_pct, 0.0, 100.0),
        ("temperature_c", temperature_c, -40.0, 90.0),
    ):
        if value is not None and not (lo <= value <= hi):
            raise ValidationApiError(f"{name} must be within [{lo}, {hi}].")
    if weight_kg is not None and not (0 <= weight_kg <= 5000):
        raise ValidationApiError("weight_kg out of range.")
    if signal_strength_dbm is not None and not (-140 <= signal_strength_dbm <= 0):
        raise ValidationApiError("signal_strength_dbm out of range.")

    reading = TelemetryReading(
        organization_id=device.organization_id,
        device_id=device.id,
        recorded_at=recorded_at,
        fill_pct=fill_pct,
        temperature_c=temperature_c,
        battery_pct=battery_pct,
        weight_kg=weight_kg,
        signal_strength_dbm=signal_strength_dbm,
        source=source,
        payload=payload,
        is_simulated=source == TelemetrySource.simulator,
    )
    session.add(reading)

    if fill_pct is not None:
        device.current_fill_pct = fill_pct
    if temperature_c is not None:
        device.current_temperature_c = temperature_c
    if battery_pct is not None:
        device.current_battery_pct = battery_pct
    device.last_telemetry_at = utcnow()
    if device.status == DeviceStatus.registered:
        device.status = DeviceStatus.active

    await _evaluate_alerts(session, device=device, reading=reading)
    return reading


async def _evaluate_alerts(session: AsyncSession, *, device: Device, reading: TelemetryReading) -> None:
    rules = (
        await session.execute(
            select(AlertRule).where(
                AlertRule.organization_id == device.organization_id, AlertRule.is_active.is_(True)
            )
        )
    ).scalars().all()

    values = {
        "fill_pct": reading.fill_pct,
        "temperature_c": reading.temperature_c,
        "battery_pct": reading.battery_pct,
        "offline_hours": None,
    }

    for rule in rules:
        if rule.device_kind and rule.device_kind != device.kind:
            continue
        value = values.get(rule.metric.value)
        if value is None:
            continue
        op = OP.get(rule.operator)
        if op is None or not op(value, rule.threshold):
            continue
        # Cooldown: skip if an alert for this rule+device exists within window
        since = utcnow() - timedelta(minutes=rule.cooldown_minutes)
        recent = (
            await session.execute(
                select(Alert.id).where(
                    Alert.rule_id == rule.id,
                    Alert.device_id == device.id,
                    Alert.triggered_at >= since,
                )
            )
        ).scalar_one_or_none()
        if recent:
            continue
        session.add(
            Alert(
                organization_id=device.organization_id,
                rule_id=rule.id,
                device_id=device.id,
                severity=rule.severity,
                title=f"{rule.name}: {device.name}",
                message=(
                    f"Device {device.device_key} ({device.name}) reported {rule.metric.value}="
                    f"{value:.1f} {rule.operator} {rule.threshold:.1f}."
                ),
                triggered_at=utcnow(),
                metadata={"value": value, "threshold": rule.threshold, "metric": rule.metric.value},
            )
        )
        if rule.severity in (AlertSeverity.high, AlertSeverity.critical):
            await notify_role(
                session,
                organization_id=device.organization_id,
                role_codes=["ops_manager", "org_admin", "field_supervisor"],
                category="alert",
                title=f"{'CRITICAL' if rule.severity == AlertSeverity.critical else 'High'} alert: {rule.name}",
                body=f"{device.name} reported {rule.metric.value}={value:.1f}.",
                data={"device_id": str(device.id), "severity": rule.severity.value},
            )


async def mark_offline_devices(session: AsyncSession, *, organization_id: uuid.UUID, hours: float = 24.0):
    """Flag devices with no telemetry in the window as offline (used by the
    offline-hours alert rule during periodic evaluation)."""
    cutoff = utcnow() - timedelta(hours=hours)
    await session.execute(
        update(Device)
        .where(
            Device.organization_id == organization_id,
            Device.status == DeviceStatus.active,
            (Device.last_telemetry_at.is_(None)) | (Device.last_telemetry_at < cutoff),
        )
        .values(status=DeviceStatus.suspended)
    )


async def device_telemetry(
    session: AsyncSession, *, organization_id: uuid.UUID, device_id: uuid.UUID, limit: int = 200
):
    return (
        await session.execute(
            select(TelemetryReading)
            .where(
                TelemetryReading.organization_id == organization_id,
                TelemetryReading.device_id == device_id,
            )
            .order_by(TelemetryReading.recorded_at.desc())
            .limit(min(limit, 1000))
        )
    ).scalars().all()
