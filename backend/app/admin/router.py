"""Platform administration + audit log endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.audit.service import list_events
from app.auth.deps import AuthCtx, DbSession, require_perm
from app.core.db import unscoped
from app.core.errors import ForbiddenError

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit", dependencies=[Depends(require_perm("audit:read"))])
async def audit_log(
    ctx: AuthCtx,
    session: DbSession,
    page: int = 1,
    page_size: int = 50,
    action_prefix: str | None = None,
    actor_user_id: uuid.UUID | None = None,
):
    items, total = await list_events(
        session,
        organization_id=ctx.org_id,
        limit=min(page_size, 200),
        offset=(page - 1) * page_size,
        action_prefix=action_prefix,
        actor_user_id=actor_user_id,
    )
    return {
        "items": [
            {
                "id": str(e.id),
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "actor_label": e.actor_label,
                "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
                "before": e.before,
                "after": e.after,
                "request_id": e.request_id,
                "created_at": e.created_at,
            }
            for e in items
        ],
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/platform/overview")
async def platform_overview(ctx: AuthCtx, session: DbSession):
    """Cross-organization stats — platform admins only."""
    if not ctx.is_platform_admin:
        raise ForbiddenError("Platform administrators only.")
    from app.orgs.models import Organization, OrgMembership

    with unscoped(session):
        orgs = (
            await session.execute(
                select(
                    Organization.id,
                    Organization.name,
                    Organization.slug,
                    Organization.org_type,
                    Organization.status,
                    Organization.is_demo,
                    Organization.created_at,
                    func.count(OrgMembership.id).label("members"),
                )
                .outerjoin(OrgMembership, OrgMembership.organization_id == Organization.id)
                .group_by(Organization.id)
                .order_by(Organization.created_at)
            )
        ).all()
    return {
        "organizations": [
            {
                "id": str(o.id), "name": o.name, "slug": o.slug,
                "org_type": o.org_type.value, "status": o.status.value,
                "is_demo": o.is_demo, "members": o.members,
                "created_at": o.created_at,
            }
            for o in orgs
        ]
    }
