"""IoT endpoints: device management, authenticated ingestion, alerts, simulator.

The ingestion endpoint is device-authenticated (X-Device-Key / X-Api-Key),
rate-limited per device, and strictly validated. The simulator endpoints are
explicitly labelled and write telemetry with source=simulator /
is_simulated=true — never silently mixed with device data.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.auth.deps import AuthCtx, DbSession, require_perm
from app.core.db import utcnow
from app.core.errors import NotFoundError, ValidationApiError
from app.core.rate_limit import rate_limit
from app.iot.models import Alert, AlertRule, AlertSeverity, Device, TelemetrySource
from app.iot.service import (
    authenticate_device,
    device_telemetry,
    ingest_telemetry,
    register_device,
    rotate_device_key,
)

router = APIRouter(prefix="/iot", tags=["iot"])
ingest_router = APIRouter(prefix="/ingest", tags=["iot"])


# --- Device management -------------------------------------------------------


class DeviceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    device_key: str | None = Field(default=None, max_length=64)
    kind: str = "fill_sensor"
    collection_point_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_simulated: bool = False


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    device_key: str
    name: str
    kind: str
    status: str
    collection_point_id: uuid.UUID | None
    zone_id: uuid.UUID | None
    latitude: float | None
    longitude: float | None
    firmware: str | None
    current_fill_pct: float | None
    current_temperature_c: float | None
    current_battery_pct: float | None
    last_telemetry_at: datetime | None
    is_simulated: bool


class DeviceWithKeyOut(DeviceOut):
    api_key: str  # returned exactly once at registration


@router.get("/devices", response_model=list[DeviceOut], dependencies=[Depends(require_perm("device:read"))])
async def list_devices(ctx: AuthCtx, session: DbSession):
    devices = (
        await session.execute(
            select(Device).where(Device.organization_id == ctx.org_id).order_by(Device.name)
        )
    ).scalars().all()
    return [DeviceOut.model_validate(d) for d in devices]


@router.post("/devices", response_model=DeviceWithKeyOut, status_code=201,
             dependencies=[Depends(require_perm("device:manage"))])
async def register_device_endpoint(body: DeviceIn, ctx: AuthCtx, session: DbSession):
    from app.audit.service import record as audit

    device, api_key = await register_device(
        session,
        organization_id=ctx.org_id,
        name=body.name,
        device_key=body.device_key,
        kind=body.kind,
        collection_point_id=body.collection_point_id,
        zone_id=body.zone_id,
        latitude=body.latitude,
        longitude=body.longitude,
        is_simulated=body.is_simulated,
    )
    await audit(
        session, action="device.register", resource_type="device", resource_id=device.id,
        organization_id=ctx.org_id, actor_user_id=ctx.user.id, actor_label=ctx.user.email,
        after={"device_key": device.device_key, "kind": body.kind},
    )
    await session.commit()
    out = DeviceOut.model_validate(device).model_dump()
    out["api_key"] = api_key
    return DeviceWithKeyOut(**out)


@router.post("/devices/{device_id}/rotate-key", dependencies=[Depends(require_perm("device:manage"))])
async def rotate_key_endpoint(device_id: uuid.UUID, ctx: AuthCtx, session: DbSession):
    from app.audit.service import record as audit

    device, api_key = await rotate_device_key(session, organization_id=ctx.org_id, device_id=device_id)
    await audit(
        session, action="device.rotate_key", resource_type="device", resource_id=device.id,
        organization_id=ctx.org_id, actor_user_id=ctx.user.id, actor_label=ctx.user.email,
    )
    await session.commit()
    return {"api_key": api_key}


@router.patch("/devices/{device_id}", dependencies=[Depends(require_perm("device:manage"))])
async def update_device(device_id: uuid.UUID, body: dict, ctx: AuthCtx, session: DbSession):
    from sqlalchemy import select as sa_select

    d = (
        await session.execute(
            sa_select(Device).where(Device.id == device_id, Device.organization_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if d is None:
        raise NotFoundError("Device not found.")
    allowed = {"name", "firmware", "latitude", "longitude", "collection_point_id", "zone_id", "status"}
    from app.iot.models import DeviceStatus

    for k, v in body.items():
        if k not in allowed:
            continue
        if k == "status":
            try:
                v = DeviceStatus(v)
            except ValueError as e:
                raise ValidationApiError(f"Unknown device status '{v}'.") from e
        setattr(d, k, v)
    await session.commit()
    return DeviceOut.model_validate(d)


@router.get("/devices/{device_id}/telemetry", dependencies=[Depends(require_perm("device:read"))])
async def device_telemetry_endpoint(device_id: uuid.UUID, ctx: AuthCtx, session: DbSession, limit: int = 200):
    from app.iot.service import get_device

    await get_device(session, ctx.org_id, device_id)  # 404 unless the device belongs to this org
    readings = await device_telemetry(session, organization_id=ctx.org_id, device_id=device_id, limit=limit)
    return {
        "items": [
            {
                "id": r.id,
                "recorded_at": r.recorded_at,
                "fill_pct": r.fill_pct,
                "temperature_c": r.temperature_c,
                "battery_pct": r.battery_pct,
                "weight_kg": r.weight_kg,
                "signal_strength_dbm": r.signal_strength_dbm,
                "source": r.source.value,
                "is_simulated": r.is_simulated,
            }
            for r in readings
        ]
    }


# --- Authenticated ingestion (devices call this) ------------------------------


class TelemetryIn(BaseModel):
    recorded_at: datetime | None = None
    fill_pct: float | None = Field(default=None, ge=0, le=100)
    temperature_c: float | None = Field(default=None, ge=-40, le=90)
    battery_pct: float | None = Field(default=None, ge=0, le=100)
    weight_kg: float | None = Field(default=None, ge=0, le=5000)
    signal_strength_dbm: float | None = Field(default=None, ge=-140, le=0)


class TelemetryBatchIn(BaseModel):
    readings: list[TelemetryIn] = Field(min_length=1, max_length=100)


@ingest_router.post("/telemetry", status_code=202, dependencies=[Depends(rate_limit("telemetry"))])
async def ingest_single(
    body: TelemetryIn,
    request: Request,
    session: DbSession,
    x_device_key: str = Header(...),
    x_api_key: str = Header(...),
):
    device = await authenticate_device(session, device_key=x_device_key, api_key=x_api_key)
    request.state.device_id = str(device.id)
    reading = await ingest_telemetry(
        session,
        device=device,
        recorded_at=body.recorded_at or utcnow(),
        fill_pct=body.fill_pct,
        temperature_c=body.temperature_c,
        battery_pct=body.battery_pct,
        weight_kg=body.weight_kg,
        signal_strength_dbm=body.signal_strength_dbm,
        source=TelemetrySource.device,
    )
    await session.commit()
    return {"accepted": True, "reading_id": reading.id}


@ingest_router.post("/telemetry/batch", status_code=202, dependencies=[Depends(rate_limit("telemetry"))])
async def ingest_batch(
    body: TelemetryBatchIn,
    request: Request,
    session: DbSession,
    x_device_key: str = Header(...),
    x_api_key: str = Header(...),
):
    device = await authenticate_device(session, device_key=x_device_key, api_key=x_api_key)
    request.state.device_id = str(device.id)
    for r in body.readings:
        await ingest_telemetry(
            session,
            device=device,
            recorded_at=r.recorded_at or utcnow(),
            fill_pct=r.fill_pct,
            temperature_c=r.temperature_c,
            battery_pct=r.battery_pct,
            weight_kg=r.weight_kg,
            signal_strength_dbm=r.signal_strength_dbm,
            source=TelemetrySource.device,
        )
    await session.commit()
    return {"accepted": True, "count": len(body.readings)}


# --- Alerts -------------------------------------------------------------------


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rule_id: uuid.UUID | None
    device_id: uuid.UUID | None
    severity: str
    title: str
    message: str | None
    status: str
    triggered_at: datetime
    acknowledged_by: uuid.UUID | None
    resolved_at: datetime | None
    metadata: dict


def _alert_out(a: Alert) -> dict:
    d = AlertOut.model_validate(
        {**{c.name: getattr(a, c.name) for c in a.__table__.columns if c.name != "metadata"},
         "metadata": a.metadata_ or {}}
    ).model_dump()
    return d


@router.get("/alerts", dependencies=[Depends(require_perm("alert:read"))])
async def list_alerts(
    ctx: AuthCtx, session: DbSession, status_filter: str | None = None,
    page: int = 1, page_size: int = 50,
):
    q = select(Alert).where(Alert.organization_id == ctx.org_id)
    if status_filter:
        q = q.where(Alert.status == status_filter)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (
        await session.execute(
            q.order_by(Alert.triggered_at.desc()).limit(min(page_size, 200)).offset((page - 1) * page_size)
        )
    ).scalars().all()
    return {
        "items": [_alert_out(a) for a in items],
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


@router.patch("/alerts/{alert_id}", dependencies=[Depends(require_perm("alert:manage"))])
async def update_alert(alert_id: uuid.UUID, body: dict, ctx: AuthCtx, session: DbSession):
    a = (
        await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.organization_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if a is None:
        raise NotFoundError("Alert not found.")
    new_status = body.get("status")
    if new_status == "acknowledged":
        a.status = "acknowledged"
        a.acknowledged_by = ctx.user.id
        a.acknowledged_at = utcnow()
    elif new_status == "resolved":
        a.status = "resolved"
        a.resolved_at = utcnow()
    await session.commit()
    return _alert_out(a)


# --- Alert rules --------------------------------------------------------------


class AlertRuleIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    metric: str  # fill_pct | temperature_c | battery_pct | offline_hours
    operator: str  # gt | gte | lt | lte
    threshold: float
    severity: str = "warning"
    cooldown_minutes: int = Field(default=60, ge=1, le=10080)
    is_active: bool = True


@router.get("/alert-rules", response_model=list[dict])
async def list_alert_rules(ctx: AuthCtx, session: DbSession):
    rules = (
        await session.execute(
            select(AlertRule).where(AlertRule.organization_id == ctx.org_id).order_by(AlertRule.name)
        )
    ).scalars().all()
    return [
        {
            "id": r.id, "name": r.name, "metric": r.metric.value, "operator": r.operator,
            "threshold": r.threshold, "severity": r.severity.value,
            "cooldown_minutes": r.cooldown_minutes, "is_active": r.is_active,
        }
        for r in rules
    ]


@router.post("/alert-rules", status_code=201, dependencies=[Depends(require_perm("alert:manage"))])
async def create_alert_rule(body: AlertRuleIn, ctx: AuthCtx, session: DbSession):
    from app.iot.models import AlertRuleMetric

    try:
        metric = AlertRuleMetric(body.metric)
    except ValueError as e:
        raise ValidationApiError(f"Unknown metric '{body.metric}'.") from e
    if body.operator not in ("gt", "gte", "lt", "lte"):
        raise ValidationApiError("operator must be gt|gte|lt|lte")
    rule = AlertRule(
        organization_id=ctx.org_id,
        name=body.name,
        metric=metric,
        operator=body.operator,
        threshold=body.threshold,
        severity=AlertSeverity(body.severity),
        cooldown_minutes=body.cooldown_minutes,
        is_active=body.is_active,
    )
    session.add(rule)
    await session.commit()
    return {"id": rule.id}
