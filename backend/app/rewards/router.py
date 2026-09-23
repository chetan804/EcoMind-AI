"""Citizen rewards: sustainability points ledger (engagement recognition only)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.auth.deps import AuthCtx, DbSession
from app.rewards.models import RewardLedger

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.get("/me")
async def my_rewards(ctx: AuthCtx, session: DbSession):
    rows = (
        await session.execute(
            select(RewardLedger).where(
                RewardLedger.organization_id == ctx.org_id,
                RewardLedger.user_id == ctx.user.id,
            ).order_by(RewardLedger.awarded_at.desc()).limit(100)
        )
    ).scalars().all()
    total = sum(r.points for r in rows)
    by_reason: dict[str, int] = {}
    for r in rows:
        by_reason[r.reason.value] = by_reason.get(r.reason.value, 0) + r.points

    # Levels are simple recognition tiers derived from actual points.
    level = 1 + total // 500
    next_level_at = level * 500

    return {
        "points": total,
        "level": level,
        "next_level_at": next_level_at,
        "by_reason": by_reason,
        "ledger": [
            {
                "points": r.points,
                "reason": r.reason.value,
                "description": r.description,
                "awarded_at": r.awarded_at,
            }
            for r in rows
        ],
    }


@router.get("/leaderboard")
async def leaderboard(ctx: AuthCtx, session: DbSession, limit: int = 10):
    from app.auth.models import User

    rows = (
        await session.execute(
            select(RewardLedger.user_id, func.sum(RewardLedger.points).label("points"))
            .where(RewardLedger.organization_id == ctx.org_id)
            .group_by(RewardLedger.user_id)
            .order_by(func.sum(RewardLedger.points).desc())
            .limit(min(limit, 50))
        )
    ).all()
    user_ids = [r.user_id for r in rows]
    names: dict = {}
    if user_ids:
        users = (
            await session.execute(select(User.id, User.full_name).where(User.id.in_(user_ids)))
        ).all()
        names = {u.id: u.full_name for u in users}
    return {
        "items": [
            {"user_id": str(r.user_id), "name": names.get(r.user_id, "Community member"),
             "points": int(r.points), "rank": i + 1}
            for i, r in enumerate(rows)
        ]
    }
