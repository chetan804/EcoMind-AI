"""Complaint management: lifecycle, SLA, assignment, comments."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select

from app.ai.service import analyze_complaint_text
from app.audit.service import record as audit
from app.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintComment,
    ComplaintPriority,
    ComplaintStatus,
)
from app.core.db import AsyncSession, utcnow
from app.core.errors import NotFoundError, ValidationApiError
from app.core.logging import get_logger
from app.notifications.service import notify_user
from app.rewards.models import RewardLedger, RewardReason

log = get_logger("complaints")

VALID_TRANSITIONS = {
    "submitted": {"triaged", "assigned", "in_progress", "resolved", "rejected"},
    "triaged": {"assigned", "in_progress", "resolved", "rejected"},
    "assigned": {"in_progress", "resolved", "rejected"},
    "in_progress": {"resolved", "rejected"},
    "resolved": {"closed"},
    "rejected": {"closed"},
    "closed": set(),
}

SLA_HOURS = {
    ComplaintPriority.urgent: 12,
    ComplaintPriority.high: 24,
    ComplaintPriority.medium: 72,
    ComplaintPriority.low: 120,
}


def sla_due_at(priority: ComplaintPriority):
    return utcnow() + timedelta(hours=SLA_HOURS[priority])


async def create_complaint(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    reporter_user_id: uuid.UUID | None,
    subject: str,
    description: str | None,
    category: str,
    priority: str | None,
    waste_report_id: uuid.UUID | None,
    zone_id: uuid.UUID | None,
    latitude: float | None,
    longitude: float | None,
    complainant_contact: str | None = None,
    run_ai: bool = True,
) -> Complaint:
    try:
        cat = ComplaintCategory(category)
    except ValueError as e:
        raise ValidationApiError(f"Unknown complaint category '{category}'.") from e

    complaint = Complaint(
        organization_id=organization_id,
        reporter_user_id=reporter_user_id,
        complainant_contact=complainant_contact,
        subject=subject,
        description=description,
        category=cat,
        status=ComplaintStatus.submitted,
        priority=ComplaintPriority.medium,
        waste_report_id=waste_report_id,
        zone_id=zone_id,
        latitude=latitude,
        longitude=longitude,
    )
    session.add(complaint)
    await session.flush()

    priority_value = priority
    if run_ai:
        inference = await analyze_complaint_text(
            session,
            organization_id=organization_id,
            subject=subject,
            description=description,
            input_ref=complaint.id,
        )
        if inference.status.value == "succeeded" and inference.output:
            suggested = inference.output.get("suggested_category")
            suggested_priority = inference.output.get("suggested_priority")
            try:
                if suggested:
                    complaint.category = ComplaintCategory(suggested)
            except ValueError:
                pass
            if suggested_priority and not priority:
                priority_value = suggested_priority

    if priority_value:
        try:
            complaint.priority = ComplaintPriority(priority_value)
        except ValueError as e:
            raise ValidationApiError(f"Unknown priority '{priority_value}'.") from e
    complaint.due_at = sla_due_at(complaint.priority)
    return complaint


async def get_complaint(session, organization_id: uuid.UUID, complaint_id: uuid.UUID) -> Complaint:
    c = (
        await session.execute(
            select(Complaint).where(
                Complaint.id == complaint_id, Complaint.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()
    if c is None:
        raise NotFoundError("Complaint not found.")
    return c


async def update_complaint(
    session: AsyncSession, *, organization_id: uuid.UUID, complaint_id: uuid.UUID,
    actor_user_id: uuid.UUID, actor_label: str, new_status: str | None = None,
    priority: str | None = None, category: str | None = None, assignee: uuid.UUID | None = None,
    resolution_summary: str | None = None, note: str | None = None,
) -> Complaint:
    c = await get_complaint(session, organization_id, complaint_id)
    before = {
        "status": c.status.value,
        "priority": c.priority.value,
        "assigned_to": str(c.assigned_to) if c.assigned_to else None,
    }
    changed = False

    if new_status:
        try:
            target = ComplaintStatus(new_status)
        except ValueError as e:
            raise ValidationApiError(f"Unknown status '{new_status}'.") from e
        allowed = VALID_TRANSITIONS.get(c.status.value, set())
        if target.value not in allowed and target != c.status:
            raise ValidationApiError(
                f"Cannot transition from '{c.status.value}' to '{target.value}'.",
                details={"allowed": sorted(allowed)},
            )
        c.status = target
        changed = True
        if target in (ComplaintStatus.triaged, ComplaintStatus.assigned, ComplaintStatus.in_progress):
            if c.first_response_at is None:
                c.first_response_at = utcnow()
        if target == ComplaintStatus.resolved:
            c.resolved_at = utcnow()
            if resolution_summary:
                c.resolution_summary = resolution_summary
            if c.reporter_user_id:
                session.add(
                    RewardLedger(
                        organization_id=organization_id,
                        user_id=c.reporter_user_id,
                        points=15,
                        reason=RewardReason.complaint_resolved,
                        description="Your complaint was resolved",
                        reference_type="complaint",
                        reference_id=c.id,
                        awarded_at=utcnow(),
                    )
                )
                await notify_user(
                    session,
                    user_id=c.reporter_user_id,
                    organization_id=organization_id,
                    category="complaint_update",
                    title="Your complaint was resolved",
                    body=resolution_summary or "Thank you for your feedback.",
                    data={"complaint_id": str(c.id), "status": "resolved"},
                )

    if priority:
        try:
            c.priority = ComplaintPriority(priority)
        except ValueError as e:
            raise ValidationApiError(f"Unknown priority '{priority}'.") from e
        c.due_at = sla_due_at(c.priority)
        changed = True

    if category:
        try:
            c.category = ComplaintCategory(category)
        except ValueError as e:
            raise ValidationApiError(f"Unknown category '{category}'.") from e
        changed = True

    if assignee is not None:
        from app.orgs.models import OrgMembership

        member = (
            await session.execute(
                select(OrgMembership).where(
                    OrgMembership.organization_id == organization_id,
                    OrgMembership.user_id == assignee,
                    OrgMembership.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if member is None:
            raise ValidationApiError("Assignee is not an active member of this organization.")
        c.assigned_to = assignee
        if c.status == ComplaintStatus.submitted:
            c.status = ComplaintStatus.assigned
        changed = True
        await notify_user(
            session,
            user_id=assignee,
            organization_id=organization_id,
            category="complaint_update",
            title="A complaint was assigned to you",
            body=c.subject,
            data={"complaint_id": str(c.id)},
        )

    if note:
        session.add(
            ComplaintComment(
                organization_id=organization_id,
                complaint_id=c.id,
                author_user_id=actor_user_id,
                body=note,
                is_internal=False,
                created_at=utcnow(),
            )
        )

    if changed:
        await audit(
            session,
            action="complaint.update",
            resource_type="complaint",
            resource_id=c.id,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_label=actor_label,
            before=before,
            after={"status": c.status.value, "priority": c.priority.value,
                   "assigned_to": str(c.assigned_to) if c.assigned_to else None},
        )
    return c


async def add_comment(
    session: AsyncSession, *, organization_id: uuid.UUID, complaint_id: uuid.UUID,
    author_user_id: uuid.UUID, body: str, is_internal: bool,
) -> ComplaintComment:
    await get_complaint(session, organization_id, complaint_id)
    comment = ComplaintComment(
        organization_id=organization_id,
        complaint_id=complaint_id,
        author_user_id=author_user_id,
        body=body,
        is_internal=is_internal,
        created_at=utcnow(),
    )
    session.add(comment)
    return comment


async def list_complaints(
    session: AsyncSession, *, organization_id: uuid.UUID, viewer_user_id: uuid.UUID | None,
    read_all: bool, status: str | None = None, priority: str | None = None,
    category: str | None = None, mine_only: bool = False, limit: int = 25, offset: int = 0,
):
    q = select(Complaint).where(Complaint.organization_id == organization_id)
    if not read_all or mine_only:
        q = q.where(
            Complaint.reporter_user_id == viewer_user_id if viewer_user_id else Complaint.reporter_user_id.is_(None)
        )
    if status:
        q = q.where(Complaint.status == status)
    if priority:
        q = q.where(Complaint.priority == priority)
    if category:
        q = q.where(Complaint.category == category)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (
        await session.execute(q.order_by(Complaint.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return items, total


async def complaint_comments(session, organization_id: uuid.UUID, complaint_id: uuid.UUID, include_internal: bool):
    q = (
        select(ComplaintComment)
        .where(
            ComplaintComment.complaint_id == complaint_id,
            ComplaintComment.organization_id == organization_id,
        )
        .order_by(ComplaintComment.created_at)
    )
    if not include_internal:
        q = q.where(ComplaintComment.is_internal.is_(False))
    return (await session.execute(q)).scalars().all()
