"""Sustainability endpoints."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.auth.deps import AuthCtx, DbSession, require_perm
from app.core.config import settings
from app.core.db import AsyncSession
from app.sustainability.models import EmissionFactor
from app.sustainability.service import period_summary, recompute_period, seed_emission_factors

router = APIRouter(prefix="/sustainability", tags=["sustainability"])


@router.get("/summary")
async def summary(
    ctx: AuthCtx,
    session: DbSession,
    days: int = Query(default=30, ge=1, le=365),
):
    end = date.today()
    start = end - timedelta(days=days - 1)
    return await period_summary(session, organization_id=ctx.org_id, period_start=start, period_end=end)


@router.post("/recompute", dependencies=[Depends(require_perm("sustainability:recompute"))])
async def recompute(
    ctx: AuthCtx,
    session: DbSession,
    days: int = Query(default=30, ge=1, le=365),
):
    end = date.today()
    start = end - timedelta(days=days - 1)
    result = await recompute_period(
        session, organization_id=ctx.org_id, period_start=start, period_end=end
    )
    await session.commit()
    return result


@router.get("/factors")
async def factors(ctx: AuthCtx, session: DbSession):
    rows = (
        await session.execute(
            select(EmissionFactor).where(EmissionFactor.is_active.is_(True)).order_by(EmissionFactor.code)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "code": f.code,
                "name": f.name,
                "category": f.category.value,
                "source": f.source,
                "year": f.year,
                "unit": f.unit,
                "value": float(f.value),
                "methodology": f.methodology,
                "version": f.version,
                "uncertainty_pct": f.uncertainty_pct,
            }
            for f in rows
        ]
    }
