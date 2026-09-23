"""Complaint endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.auth.deps import AuthCtx, DbSession, require_perm
from app.complaints.models import Complaint, ComplaintComment
from app.complaints.schemas import ComplaintCreate, ComplaintOut, ComplaintUpdateIn
from app.complaints.service import (
    add_comment,
    complaint_comments,
    create_complaint,
    get_complaint,
    list_complaints,
    update_complaint,
)
from app.core.errors import ValidationApiError
from app.core.rate_limit import rate_limit

router = APIRouter(prefix="/complaints", tags=["complaints"])


async def _complaint_out(session, c: Complaint, include_ai: bool = True) -> dict:
    reporter_name = assignee_name = None
    from app.auth.models import User

    if c.reporter_user_id:
        reporter_name = (
            await session.execute(select(User.full_name).where(User.id == c.reporter_user_id))
        ).scalar_one_or_none()
    if c.assigned_to:
        assignee_name = (
            await session.execute(select(User.full_name).where(User.id == c.assigned_to))
        ).scalar_one_or_none()
    out = ComplaintOut.model_validate(c).model_dump()
    out.update(reporter_name=reporter_name, assignee_name=assignee_name)
    return out


@router.post("", response_model=ComplaintOut, status_code=201, dependencies=[Depends(rate_limit("write"))])
async def create_complaint_endpoint(body: ComplaintCreate, ctx: AuthCtx, session: DbSession):
    complaint = await create_complaint(
        session,
        organization_id=ctx.org_id,
        reporter_user_id=ctx.user.id,
        subject=body.subject,
        description=body.description,
        category=body.category,
        priority=body.priority,
        waste_report_id=body.waste_report_id,
        zone_id=body.zone_id,
        latitude=body.latitude,
        longitude=body.longitude,
    )
    await session.commit()
    return await _complaint_out(session, complaint)


@router.get("")
async def list_complaints_endpoint(
    ctx: AuthCtx,
    session: DbSession,
    page: int = 1,
    page_size: int = 25,
    status_filter: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    mine: bool = False,
):
    items, total = await list_complaints(
        session,
        organization_id=ctx.org_id,
        viewer_user_id=ctx.user.id,
        read_all=ctx.has_perm("complaint:read_all"),
        status=status_filter,
        priority=priority,
        category=category,
        mine_only=mine,
        limit=min(page_size, 100),
        offset=(page - 1) * page_size,
    )
    return {
        "items": [await _complaint_out(session, c) for c in items],
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/{complaint_id}")
async def get_complaint_endpoint(complaint_id: uuid.UUID, ctx: AuthCtx, session: DbSession):
    c = await get_complaint(session, ctx.org_id, complaint_id)
    ctx.ensure_perm("complaint:read_all", "complaint:read", c.reporter_user_id)
    return await _complaint_out(session, c)


@router.patch("/{complaint_id}", response_model=ComplaintOut)
async def update_complaint_endpoint(complaint_id: uuid.UUID, body: ComplaintUpdateIn, ctx: AuthCtx, session: DbSession):
    c = await get_complaint(session, ctx.org_id, complaint_id)
    ctx.ensure_perm("complaint:triage", "complaint:read", c.reporter_user_id)
    if body.new_status in ("resolved", "rejected") and not ctx.has_perm("complaint:resolve"):
        ctx.require_perm("complaint:resolve")
    if body.assignee and not ctx.has_perm("complaint:assign"):
        ctx.require_perm("complaint:assign")
    c = await update_complaint(
        session,
        organization_id=ctx.org_id,
        complaint_id=complaint_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        new_status=body.new_status,
        priority=body.priority,
        category=body.category,
        assignee=body.assignee,
        resolution_summary=body.resolution_summary,
        note=body.note,
    )
    await session.commit()
    return await _complaint_out(session, c)


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    is_internal: bool = False


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    author_user_id: uuid.UUID | None
    author_name: str | None = None
    body: str
    is_internal: bool
    created_at: datetime


@router.post("/{complaint_id}/comments", response_model=CommentOut, status_code=201)
async def add_comment_endpoint(complaint_id: uuid.UUID, body: CommentIn, ctx: AuthCtx, session: DbSession):
    c = await get_complaint(session, ctx.org_id, complaint_id)
    if body.is_internal and not ctx.has_perm("complaint:comment"):
        raise ValidationApiError("Internal notes require staff permission.")
    ctx.ensure_perm("complaint:comment", "complaint:read", c.reporter_user_id)
    comment = await add_comment(
        session,
        organization_id=ctx.org_id,
        complaint_id=complaint_id,
        author_user_id=ctx.user.id,
        body=body.body,
        is_internal=body.is_internal,
    )
    await session.commit()
    from app.auth.models import User

    name = (
        await session.execute(select(User.full_name).where(User.id == ctx.user.id))
    ).scalar_one_or_none()
    return CommentOut(
        id=comment.id,
        author_user_id=comment.author_user_id,
        author_name=name,
        body=comment.body,
        is_internal=comment.is_internal,
        created_at=comment.created_at,
    )


@router.get("/{complaint_id}/comments", response_model=list[CommentOut])
async def list_comments_endpoint(complaint_id: uuid.UUID, ctx: AuthCtx, session: DbSession):
    c = await get_complaint(session, ctx.org_id, complaint_id)
    ctx.ensure_perm("complaint:comment", "complaint:read", c.reporter_user_id)
    include_internal = ctx.has_perm("complaint:comment")
    comments = await complaint_comments(session, ctx.org_id, complaint_id, include_internal)
    from app.auth.models import User

    out = []
    for cm in comments:
        name = None
        if cm.author_user_id:
            name = (
                await session.execute(select(User.full_name).where(User.id == cm.author_user_id))
            ).scalar_one_or_none()
        out.append(
            CommentOut(
                id=cm.id, author_user_id=cm.author_user_id, author_name=name,
                body=cm.body, is_internal=cm.is_internal, created_at=cm.created_at,
            )
        )
    return out
