"""Fleet endpoints: vehicles, driver profiles, position updates."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.audit.service import record as audit
from app.auth.deps import AuthCtx, DbSession, require_perm
from app.core.errors import NotFoundError, ValidationApiError
from app.fleet.models import DriverProfile, FuelType, Vehicle, VehicleStatus, VehicleType

router = APIRouter(prefix="/fleet", tags=["fleet"])


class VehicleIn(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str | None = None
    unit_id: uuid.UUID | None = None
    vehicle_type: str = "compactor_truck"
    fuel_type: str = "diesel"
    plate_number: str | None = None
    capacity_kg: float | None = Field(default=None, ge=0, le=100_000)
    capacity_volume_m3: float | None = Field(default=None, ge=0, le=500)
    depot_lat: float | None = None
    depot_lng: float | None = None
    notes: str | None = None


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str | None
    unit_id: uuid.UUID | None
    vehicle_type: str
    fuel_type: str
    plate_number: str | None
    capacity_kg: float | None
    capacity_volume_m3: float | None
    status: str
    odometer_km: float | None
    depot_lat: float | None
    depot_lng: float | None
    current_lat: float | None
    current_lng: float | None
    current_route_id: uuid.UUID | None
    last_ping_at: datetime | None
    position_is_simulated: bool
    notes: str | None


def _vout(v: Vehicle) -> VehicleOut:
    out = VehicleOut.model_validate(v).model_dump()
    out["capacity_kg"] = float(v.capacity_kg) if v.capacity_kg is not None else None
    out["capacity_volume_m3"] = float(v.capacity_volume_m3) if v.capacity_volume_m3 is not None else None
    out["odometer_km"] = float(v.odometer_km) if v.odometer_km is not None else None
    return VehicleOut(**out)


@router.get("/vehicles", response_model=list[VehicleOut], dependencies=[Depends(require_perm("fleet:read"))])
async def list_vehicles(ctx: AuthCtx, session: DbSession):
    vs = (
        await session.execute(
            select(Vehicle).where(Vehicle.organization_id == ctx.org_id).order_by(Vehicle.code)
        )
    ).scalars().all()
    return [_vout(v) for v in vs]


@router.post("/vehicles", response_model=VehicleOut, status_code=201,
             dependencies=[Depends(require_perm("fleet:manage"))])
async def create_vehicle(body: VehicleIn, ctx: AuthCtx, session: DbSession):
    dupe = (
        await session.execute(
            select(Vehicle.id).where(Vehicle.organization_id == ctx.org_id, Vehicle.code == body.code)
        )
    ).scalar_one_or_none()
    if dupe:
        raise ValidationApiError("Vehicle code already exists.")
    try:
        v = Vehicle(
            organization_id=ctx.org_id,
            code=body.code,
            name=body.name,
            unit_id=body.unit_id,
            vehicle_type=VehicleType(body.vehicle_type),
            fuel_type=FuelType(body.fuel_type),
            plate_number=body.plate_number,
            capacity_kg=body.capacity_kg,
            capacity_volume_m3=body.capacity_volume_m3,
            depot_lat=body.depot_lat,
            depot_lng=body.depot_lng,
            notes=body.notes,
        )
    except ValueError as e:
        raise ValidationApiError(f"Unknown vehicle/fuel type: {e}") from e
    session.add(v)
    await audit(
        session, action="vehicle.create", resource_type="vehicle", resource_id=v.id,
        organization_id=ctx.org_id, actor_user_id=ctx.user.id, actor_label=ctx.user.email,
        after={"code": v.code, "vehicle_type": v.vehicle_type.value, "fuel_type": v.fuel_type.value},
    )
    await session.commit()
    return _vout(v)


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut,
              dependencies=[Depends(require_perm("fleet:manage"))])
async def update_vehicle(vehicle_id: uuid.UUID, body: dict, ctx: AuthCtx, session: DbSession):
    v = (
        await session.execute(
            select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.organization_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if v is None:
        raise NotFoundError("Vehicle not found.")
    allowed = {"name", "status", "plate_number", "capacity_kg", "capacity_volume_m3", "odometer_km",
               "depot_lat", "depot_lng", "notes", "unit_id"}
    for k, val in body.items():
        if k not in allowed:
            continue
        if k == "status":
            val = VehicleStatus(val)
        setattr(v, k, val)
    await session.commit()
    return _vout(v)


class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    full_name: str | None = None
    license_number: str | None
    license_expiry: datetime | None
    default_vehicle_id: uuid.UUID | None
    is_active: bool


@router.get("/drivers", response_model=list[DriverOut], dependencies=[Depends(require_perm("fleet:read"))])
async def list_drivers(ctx: AuthCtx, session: DbSession):
    from app.auth.models import User

    rows = (
        await session.execute(
            select(DriverProfile, User.full_name)
            .join(User, User.id == DriverProfile.user_id)
            .where(DriverProfile.organization_id == ctx.org_id, DriverProfile.is_active.is_(True))
        )
    ).all()
    return [
        DriverOut(
            user_id=dp.user_id,
            full_name=name,
            license_number=dp.license_number,
            license_expiry=dp.license_expiry,
            default_vehicle_id=dp.default_vehicle_id,
            is_active=dp.is_active,
        )
        for dp, name in rows
    ]


@router.post("/drivers", response_model=DriverOut, status_code=201,
             dependencies=[Depends(require_perm("fleet:manage"))])
async def upsert_driver(body: dict, ctx: AuthCtx, session: DbSession):
    from app.orgs.models import OrgMembership

    user_id = body.get("user_id")
    if not user_id:
        raise ValidationApiError("user_id required.")
    member = (
        await session.execute(
            select(OrgMembership).where(
                OrgMembership.organization_id == ctx.org_id, OrgMembership.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise ValidationApiError("User is not a member of this organization.")
    dp = (
        await session.execute(
            select(DriverProfile).where(
                DriverProfile.organization_id == ctx.org_id, DriverProfile.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if dp is None:
        dp = DriverProfile(organization_id=ctx.org_id, user_id=user_id)
        session.add(dp)
    dp.license_number = body.get("license_number", dp.license_number)
    dp.default_vehicle_id = body.get("default_vehicle_id", dp.default_vehicle_id)
    await session.commit()
    return DriverOut(
        user_id=dp.user_id,
        license_number=dp.license_number,
        license_expiry=dp.license_expiry,
        default_vehicle_id=dp.default_vehicle_id,
        is_active=dp.is_active,
    )
