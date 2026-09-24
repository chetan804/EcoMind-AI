"""AI endpoints: provider status, inference list, human review."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.ai.providers import provider_status
from app.ai.service import list_inferences, submit_review
from app.auth.deps import AuthCtx, DbSession, require_perm

router = APIRouter(prefix="/ai", tags=["ai"])


class InferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    task: str
    status: str
    provider: str
    model: str
    input_type: str
    input_summary: str | None
    output: dict | None
    confidence: float | None
    latency_ms: int | None
    error_code: str | None
    error_message: str | None
    is_simulated: bool
    reviewed_by: uuid.UUID | None
    created_at: datetime


class ReviewIn(BaseModel):
    decision: str  # confirmed | corrected | rejected
    corrected_output: dict | None = None
    note: str | None = None


@router.get("/providers")
async def providers_status(_: AuthCtx):
    """Which providers are configured. The baseline is always available and clearly labelled."""
    return {"items": provider_status()}


@router.get("/inferences", dependencies=[Depends(require_perm("ai:read"))])
async def list_inferences_endpoint(
    ctx: AuthCtx,
    session: DbSession,
    status: str | None = None,
    task: str | None = None,
    page: int = 1,
    page_size: int = 25,
):
    items, total = await list_inferences(
        session,
        organization_id=ctx.org_id,
        status=status,
        task=task,
        limit=min(page_size, 100),
        offset=(page - 1) * page_size,
    )
    return {
        "items": [InferenceOut.model_validate(i).model_dump() for i in items],
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


@router.post("/inferences/{inference_id}/review", dependencies=[Depends(require_perm("ai:review"))])
async def review_endpoint(inference_id: uuid.UUID, body: ReviewIn, ctx: AuthCtx, session: DbSession):
    inf = await submit_review(
        session,
        organization_id=ctx.org_id,
        inference_id=inference_id,
        reviewer_user_id=ctx.user.id,
        decision=body.decision,
        corrected_output=body.corrected_output,
        note=body.note,
    )
    await session.commit()
    return InferenceOut.model_validate(inf)
