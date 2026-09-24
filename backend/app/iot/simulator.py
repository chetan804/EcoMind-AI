"""Telemetry simulator — EXPLICITLY LABELLED SIMULATED DATA.

Purpose: demonstrations and load-testing without hardware. Everything this
module writes carries ``source='simulator'`` / ``is_simulated=True`` and
devices it manages are flagged ``is_simulated=True``. The demo UI shows a
SIMULATION badge on this data. Real device ingestion is a separate,
independently authenticated path and can never be produced by this module.
"""

from __future__ import annotations

import random
import uuid

from sqlalchemy import select

from app.core.db import AsyncSession, utcnow
from app.core.logging import get_logger
from app.iot.models import Device, TelemetrySource
from app.iot.service import ingest_telemetry

log = get_logger("simulator")


async def tick(session: AsyncSession, *, organization_id: uuid.UUID) -> dict:
    """Advance every simulated device one step: fill drifts up, temperature
    wobbles, battery drains. Overflow and anomalies occur occasionally."""
    devices = (
        await session.execute(
            select(Device).where(
                Device.organization_id == organization_id, Device.is_simulated.is_(True)
            )
        )
    ).scalars().all()
    updated = 0
    for d in devices:
        fill = d.current_fill_pct if d.current_fill_pct is not None else random.uniform(10, 40)
        battery = d.current_battery_pct if d.current_battery_pct is not None else random.uniform(70, 100)
        temp = d.current_temperature_c if d.current_temperature_c is not None else random.uniform(18, 32)

        fill = min(100.0, max(0.0, fill + random.uniform(2.0, 9.0)))
        battery = max(0.0, battery - random.uniform(0.05, 0.4))
        temp = max(10.0, min(75.0, temp + random.uniform(-1.5, 1.5)))
        if random.random() < 0.02:  # occasional anomaly spike
            temp = random.uniform(55, 70)

        await ingest_telemetry(
            session,
            device=d,
            recorded_at=utcnow(),
            fill_pct=round(fill, 1),
            temperature_c=round(temp, 1),
            battery_pct=round(battery, 1),
            weight_kg=None,
            signal_strength_dbm=round(random.uniform(-95, -50), 1),
            source=TelemetrySource.simulator,
        )
        updated += 1
    return {"simulated_devices_updated": updated}


async def ensure_simulated_devices(
    session: AsyncSession, *, organization_id: uuid.UUID, count: int, points: list
) -> list[Device]:
    """Create the simulated fleet for a demo organization (idempotent)."""
    from app.iot.service import register_device

    existing = (
        await session.execute(
            select(Device).where(
                Device.organization_id == organization_id, Device.is_simulated.is_(True)
            )
        )
    ).scalars().all()
    if len(existing) >= count:
        return existing[:count]
    devices = list(existing)
    for i in range(count - len(existing)):
        point = points[i % len(points)] if points else None
        device, _key = await register_device(
            session,
            organization_id=organization_id,
            name=f"SIM Bin Sensor {i + 1:02d}",
            device_key=f"SIM-{uuid.uuid4().hex[:8].upper()}",
            kind="fill_sensor",
            collection_point_id=point.id if point else None,
            zone_id=point.zone_id if point else None,
            latitude=point.latitude if point else None,
            longitude=point.longitude if point else None,
            is_simulated=True,
        )
        devices.append(device)
    return devices
