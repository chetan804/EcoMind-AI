"""Job handlers. Every handler receives (session, payload, organization_id)."""

from __future__ import annotations

import uuid
from datetime import date

from app.core.logging import get_logger
from app.jobs.queue import register

log = get_logger("jobs.handlers")


@register("route_optimize")
async def route_optimize(session, payload: dict, organization_id: uuid.UUID | None):
    from app.routing.service import generate_route

    await generate_route(
        session,
        organization_id=organization_id,
        name=payload["name"],
        service_date=date.fromisoformat(payload["service_date"]),
        depot_lat=payload["depot_lat"],
        depot_lng=payload["depot_lng"],
        zone_id=uuid.UUID(payload["zone_id"]) if payload.get("zone_id") else None,
        created_by=uuid.UUID(payload["created_by"]) if payload.get("created_by") else None,
    )
    await session.commit()


@register("simulator_tick")
async def simulator_tick(session, payload: dict, organization_id: uuid.UUID | None):
    """Advance the DEMO simulation one step. Writes only is_simulated=true data."""
    from app.iot.simulator import tick

    result = await tick(session, organization_id=organization_id)
    await session.commit()
    log.info("simulator_tick_done", org=str(organization_id), **result)


@register("sustainability_recompute")
async def sustainability_recompute(session, payload: dict, organization_id: uuid.UUID | None):
    from app.sustainability.service import recompute_period

    end = date.fromisoformat(payload["end"])
    start = date.fromisoformat(payload["start"])
    result = await recompute_period(session, organization_id=organization_id, period_start=start, period_end=end)
    await session.commit()
    log.info("sustainability_recomputed", org=str(organization_id), **result)


@register("demo_simulator_schedule")
async def demo_simulator_schedule(session, payload: dict, organization_id: uuid.UUID | None):
    """Re-schedule the demo simulator tick — a self-perpetuating labelled demo loop."""
    from datetime import timedelta

    from app.core.db import utcnow
    from app.jobs.queue import enqueue

    from app.iot.simulator import tick

    await tick(session, organization_id=organization_id)
    await session.commit()
    await enqueue(
        session,
        kind="demo_simulator_schedule",
        organization_id=organization_id,
        run_after=utcnow() + timedelta(seconds=payload.get("interval_seconds", 30)),
        priority=-10,
    )
    await session.commit()
