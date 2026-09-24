"""Analytics endpoints (role dashboards) + CSV export."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.analytics.service import citizen_dashboard, executive_dashboard, operations_dashboard
from app.auth.deps import AuthCtx, DbSession, require_perm
from app.collection.models import CollectionEvent
from app.waste.models import WasteReport

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/operations", dependencies=[Depends(require_perm("analytics:read"))])
async def operations(ctx: AuthCtx, session: DbSession, days: int = Query(default=30, ge=1, le=365)):
    return await operations_dashboard(session, organization_id=ctx.org_id, days=days)


@router.get("/citizen")
async def citizen(ctx: AuthCtx, session: DbSession, days: int = Query(default=30, ge=1, le=365)):
    return await citizen_dashboard(session, organization_id=ctx.org_id, user_id=ctx.user.id, days=days)


@router.get("/executive", dependencies=[Depends(require_perm("analytics:read"))])
async def executive(ctx: AuthCtx, session: DbSession, days: int = Query(default=90, ge=1, le=365)):
    return await executive_dashboard(session, organization_id=ctx.org_id, days=days)


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    if not rows:
        rows = [{"message": "no data for this period"}]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/collections.csv", dependencies=[Depends(require_perm("analytics:read"))])
async def export_collections(ctx: AuthCtx, session: DbSession, days: int = Query(default=30, ge=1, le=365)):
    since = date.today() - timedelta(days=days - 1)
    rows = (
        await session.execute(
            select(
                CollectionEvent.scheduled_date.label("date"),
                CollectionEvent.collection_point_id.label("point_id"),
                CollectionEvent.status.label("status"),
                CollectionEvent.weight_kg.label("weight_kg"),
                CollectionEvent.vehicle_id.label("vehicle_id"),
                CollectionEvent.route_id.label("route_id"),
            ).where(
                CollectionEvent.organization_id == ctx.org_id,
                CollectionEvent.scheduled_date >= since,
            ).order_by(CollectionEvent.scheduled_date)
        )
    ).mappings().all()
    data = [
        {
            "date": str(r["date"]), "point_id": str(r["point_id"]), "status": r["status"].value,
            "weight_kg": float(r["weight_kg"]) if r["weight_kg"] is not None else "",
            "vehicle_id": str(r["vehicle_id"] or ""), "route_id": str(r["route_id"] or ""),
        }
        for r in rows
    ]
    return _csv_response(data, f"collections_{ctx.org.slug}_{since}_to_{date.today()}.csv")


@router.get("/export/reports.csv", dependencies=[Depends(require_perm("analytics:read"))])
async def export_reports(ctx: AuthCtx, session: DbSession, days: int = Query(default=30, ge=1, le=365)):
    since = date.today() - timedelta(days=days - 1)
    rows = (
        await session.execute(
            select(
                WasteReport.created_at.label("created_at"),
                WasteReport.status.label("status"),
                WasteReport.severity.label("severity"),
                WasteReport.latitude.label("lat"),
                WasteReport.longitude.label("lng"),
                WasteReport.is_anonymous.label("anonymous"),
            ).where(
                WasteReport.organization_id == ctx.org_id,
                WasteReport.created_at >= since,
            ).order_by(WasteReport.created_at)
        )
    ).mappings().all()
    data = [
        {
            "created_at": r["created_at"].isoformat(), "status": r["status"].value,
            "severity": r["severity"].value, "lat": r["lat"], "lng": r["lng"],
            "anonymous": r["anonymous"],
        }
        for r in rows
    ]
    return _csv_response(data, f"reports_{ctx.org.slug}_{since}_to_{date.today()}.csv")
