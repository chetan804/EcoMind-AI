"""Collection service: points, schedules, events, completion logic."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select

from app.audit.service import record as audit
from app.collection.models import (
    CollectionEvent,
    CollectionPoint,
    CollectionSchedule,
    EventStatus,
    PointKind,
    ScheduleFrequency,
)
from app.core.db import AsyncSession, utcnow
from app.core.errors import NotFoundError, ValidationApiError
from app.sustainability.models import DataQuality, WasteTreatment


async def create_point(session: AsyncSession, *, organization_id: uuid.UUID, **kwargs):
    dupe = (
        await session.execute(
            select(CollectionPoint.id).where(
                CollectionPoint.organization_id == organization_id,
                CollectionPoint.code == kwargs["code"],
            )
        )
    ).scalar_one_or_none()
    if dupe:
        raise ValidationApiError("Collection point code already exists.")
    try:
        kind = PointKind(kwargs.get("kind", "bin_station"))
    except ValueError as e:
        raise ValidationApiError(f"Unknown point kind '{kwargs['kind']}'.") from e
    pt = CollectionPoint(organization_id=organization_id, kind=kind, **{k: v for k, v in kwargs.items() if k != "kind"})
    session.add(pt)
    await session.flush()
    return pt


async def create_schedule(
    session: AsyncSession, *, organization_id: uuid.UUID, collection_point_id: uuid.UUID,
    waste_category_id: uuid.UUID | None, frequency: str, weekday: int | None,
    start_date: date, window_start: str | None, window_end: str | None,
):
    try:
        freq = ScheduleFrequency(frequency)
    except ValueError as e:
        raise ValidationApiError(f"Unknown frequency '{frequency}'.") from e
    if freq in (ScheduleFrequency.weekly, ScheduleFrequency.biweekly) and weekday is None:
        raise ValidationApiError("weekly/biweekly schedules require a weekday (0=Mon).")
    pt = (
        await session.execute(
            select(CollectionPoint).where(
                CollectionPoint.id == collection_point_id,
                CollectionPoint.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if pt is None:
        raise NotFoundError("Collection point not found.")
    s = CollectionSchedule(
        organization_id=organization_id,
        collection_point_id=collection_point_id,
        waste_category_id=waste_category_id,
        frequency=freq,
        weekday=weekday,
        start_date=start_date,
    )
    session.add(s)
    await session.flush()
    return s


def _event_out_row(event, pt_map):
    d = {
        "id": event.id,
        "collection_point_id": event.collection_point_id,
        "point_name": pt_map.get(event.collection_point_id, {}).get("name"),
        "point_code": pt_map.get(event.collection_point_id, {}).get("code"),
        "waste_category_id": event.waste_category_id,
        "scheduled_date": event.scheduled_date,
        "status": event.status.value,
        "route_id": event.route_id,
        "vehicle_id": event.vehicle_id,
        "collector_user_id": event.collector_user_id,
        "completed_at": event.completed_at,
        "weight_kg": float(event.weight_kg) if event.weight_kg is not None else None,
        "contamination_flag": event.contamination_flag,
        "skip_reason": event.skip_reason,
        "notes": event.notes,
    }
    return d


async def list_events(
    session: AsyncSession, *, organization_id: uuid.UUID, date_from: date | None,
    date_to: date | None, status: str | None, limit: int, offset: int,
):
    q = select(CollectionEvent).where(CollectionEvent.organization_id == organization_id)
    if date_from:
        q = q.where(CollectionEvent.scheduled_date >= date_from)
    if date_to:
        q = q.where(CollectionEvent.scheduled_date <= date_to)
    if status:
        try:
            st = EventStatus(status)
        except ValueError as e:
            raise ValidationApiError(f"Unknown status '{status}'.") from e
        q = q.where(CollectionEvent.status == st)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (
        await session.execute(q.order_by(CollectionEvent.scheduled_date.desc()).limit(limit).offset(offset))
    ).scalars().all()
    pt_ids = {e.collection_point_id for e in items}
    pt_map: dict = {}
    if pt_ids:
        pts = (
            await session.execute(
                select(CollectionPoint).where(CollectionPoint.id.in_(pt_ids))
            )
        ).scalars().all()
        pt_map = {p.id: {"name": p.name, "code": p.code} for p in pts}
    return [_event_out_row(e, pt_map) for e in items], total


async def complete_event(
    session: AsyncSession, *, organization_id: uuid.UUID, event_id: uuid.UUID,
    collector_user_id: uuid.UUID, status: str, weight_kg: float | None,
    contamination_flag: bool, skip_reason: str | None, notes: str | None,
) -> CollectionEvent:
    event = (
        await session.execute(
            select(CollectionEvent).where(
                CollectionEvent.id == event_id, CollectionEvent.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()
    if event is None:
        raise NotFoundError("Collection event not found.")
    try:
        target = EventStatus(status)
    except ValueError as e:
        raise ValidationApiError(f"Unknown status '{status}'.") from e
    if event.status == EventStatus.completed:
        raise ValidationApiError("Event already completed.")
    before = {"status": event.status.value, "weight_kg": float(event.weight_kg) if event.weight_kg else None}
    event.status = target
    event.collector_user_id = collector_user_id
    if weight_kg is not None:
        event.weight_kg = weight_kg
    event.contamination_flag = contamination_flag
    event.skip_reason = skip_reason
    event.notes = notes
    if target == EventStatus.completed:
        event.completed_at = utcnow()
        # Completed collections with weight feed the sustainability activity data.
        if weight_kg and weight_kg > 0:
            category = event.waste_category_id
            destination = await _default_destination(session, organization_id, category)
            session.add(
                WasteTreatment(
                    organization_id=organization_id,
                    treatment_date=event.scheduled_date,
                    waste_category_id=category,
                    destination=destination,
                    weight_kg=weight_kg,
                    quality=DataQuality.measured,
                    source_event_id=event.id,
                )
            )
    await audit(
        session,
        action="collection_event.complete",
        resource_type="collection_event",
        resource_id=event.id,
        organization_id=organization_id,
        actor_user_id=collector_user_id,
        before=before,
        after={"status": target.value, "weight_kg": weight_kg},
    )
    return event


async def _default_destination(session, organization_id: uuid.UUID, waste_category_id) -> str:
    """Map a waste category to its default treatment destination."""
    from app.waste.models import WasteCategory

    if waste_category_id is None:
        return "landfill"
    cat = (
        await session.execute(
            select(WasteCategory).where(WasteCategory.id == waste_category_id)
        )
    ).scalar_one_or_none()
    if cat is None:
        return "landfill"
    return {
        "recyclable": "recycling",
        "organic": "composting",
        "mixed": "landfill",
        "hazardous": "secure_disposal",
        "e_waste": "recycling",
        "construction": "landfill",
    }.get(cat.code, "landfill")
