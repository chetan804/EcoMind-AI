"""AI inference pipeline: validate → run → validate → confidence gate → persist.

Every inference is a database row with provider, model, latency, structured
output and status. Low-confidence results and provider failures route to the
human-review queue instead of silently proceeding. Simulated demo inferences
carry ``is_simulated=True`` and are labelled in every API response.
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy import func, select

from app.ai.models import AiInference, AiStatus, AiTask
from app.ai.providers import AiProvider, AiProviderError, get_provider
from app.ai.schemas import (
    ComplaintAnalysisOut,
    WasteClass,
    WasteClassificationOut,
)
from app.core.config import settings
from app.core.db import AsyncSession, utcnow
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.core.storage import get_storage

log = get_logger("ai")

DEFAULT_CONFIDENCE_THRESHOLD = 0.75


def confidence_threshold(org) -> float:
    return float((org.settings or {}).get("ai_confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD))


async def _persist_start(
    session: AsyncSession, *, organization_id: uuid.UUID, task: AiTask, provider: AiProvider,
    input_type: str, input_summary: str | None, media_id: uuid.UUID | None, input_ref: uuid.UUID | None,
) -> AiInference:
    inf = AiInference(
        organization_id=organization_id,
        task=task,
        status=AiStatus.pending,
        provider=provider.name,
        model=getattr(provider, "model", "rules-v1"),
        input_type=input_type,
        input_summary=(input_summary or "")[:2000] or None,
        media_id=media_id,
        input_ref=input_ref,
    )
    session.add(inf)
    await session.flush()
    return inf


async def classify_waste_report(
    session: AsyncSession, *, organization_id: uuid.UUID, description: str | None,
    media_id: uuid.UUID | None, media_storage_key: str | None, media_mime: str | None,
    input_ref: uuid.UUID | None = None, provider_name: str | None = None,
) -> AiInference:
    """Full classification pipeline for one report. Never raises for provider
    failures — the inference row records the failure and requests review."""
    provider = get_provider(provider_name)
    threshold = await _org_threshold(session, organization_id)

    image_bytes = None
    if media_storage_key:
        try:
            image_bytes = get_storage().open(media_storage_key)
            if len(image_bytes) > settings.ai_max_image_bytes:
                image_bytes = None
        except Exception:
            image_bytes = None

    inf = await _persist_start(
        session,
        organization_id=organization_id,
        task=AiTask.waste_classification,
        provider=provider,
        input_type="image" if image_bytes else "text",
        input_summary=description,
        media_id=media_id,
        input_ref=input_ref,
    )

    started = time.perf_counter()
    result: WasteClassificationOut | None = None
    error: AiProviderError | None = None
    for attempt in (1, 2):
        try:
            result = await provider.classify_waste(
                image_bytes=image_bytes, mime=media_mime, text_hint=description
            )
            break
        except AiProviderError as e:
            error = e
            if not e.retryable or attempt == 2:
                break
        except Exception as e:  # validation errors from strict pydantic parsing
            error = AiProviderError(provider.name, f"Invalid structured output: {e}", retryable=False)
            break
    latency_ms = int((time.perf_counter() - started) * 1000)

    if result is None:
        inf.status = AiStatus.failed
        inf.error_code = (error.code if hasattr(error, "code") else "provider_error")
        inf.error_message = str(error)[:2000] if error else "unknown"
        inf.latency_ms = latency_ms
        await session.flush()
        return inf

    # --- Trust gate: schema already enforced by pydantic; now business rules ---
    needs_review = result.confidence < threshold or result.category == WasteClass.unknown
    inf.status = AiStatus.needs_review if needs_review else AiStatus.succeeded
    inf.output = result.model_dump(mode="json")
    inf.confidence = result.confidence
    inf.latency_ms = latency_ms
    await session.flush()
    return inf


async def analyze_complaint_text(
    session: AsyncSession, *, organization_id: uuid.UUID, subject: str, description: str | None,
    input_ref: uuid.UUID | None = None, provider_name: str | None = None,
) -> AiInference:
    provider = get_provider(provider_name)
    inf = await _persist_start(
        session,
        organization_id=organization_id,
        task=AiTask.complaint_classification,
        provider=provider,
        input_type="text",
        input_summary=f"{subject} — {description or ''}",
        media_id=None,
        input_ref=input_ref,
    )
    started = time.perf_counter()
    try:
        result = await provider.analyze_complaint(subject=subject, description=description or "")
        latency_ms = int((time.perf_counter() - started) * 1000)
        inf.output = result.model_dump(mode="json")
        inf.confidence = result.confidence
        inf.latency_ms = latency_ms
        inf.status = AiStatus.succeeded  # suggestion-only task; operator decides
    except AiProviderError as e:
        inf.status = AiStatus.failed
        inf.error_code = "provider_error"
        inf.error_message = str(e)[:2000]
        inf.latency_ms = int((time.perf_counter() - started) * 1000)
    except Exception as e:
        inf.status = AiStatus.failed
        inf.error_code = "invalid_output"
        inf.error_message = str(e)[:2000]
        inf.latency_ms = int((time.perf_counter() - started) * 1000)
    await session.flush()
    return inf


async def _org_threshold(session: AsyncSession, organization_id: uuid.UUID) -> float:
    from app.orgs.models import Organization

    org = (
        await session.execute(select(Organization).where(Organization.id == organization_id))
    ).scalar_one_or_none()
    return confidence_threshold(org) if org else DEFAULT_CONFIDENCE_THRESHOLD


async def list_inferences(
    session: AsyncSession, *, organization_id: uuid.UUID, status: str | None = None,
    task: str | None = None, limit: int = 50, offset: int = 0,
):
    q = select(AiInference).where(AiInference.organization_id == organization_id)
    if status:
        q = q.where(AiInference.status == status)
    if task:
        q = q.where(AiInference.task == task)
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (
        await session.execute(q.order_by(AiInference.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return items, total


async def submit_review(
    session: AsyncSession, *, organization_id: uuid.UUID, inference_id: uuid.UUID,
    reviewer_user_id: uuid.UUID, decision: str, corrected_output: dict | None, note: str | None,
):
    from app.ai.models import AiReview

    inf = (
        await session.execute(
            select(AiInference).where(
                AiInference.id == inference_id, AiInference.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()
    if inf is None:
        raise NotFoundError("Inference not found.")
    if decision not in {"confirmed", "corrected", "rejected"}:
        from app.core.errors import ValidationApiError

        raise ValidationApiError("decision must be confirmed | corrected | rejected")
    session.add(
        AiReview(
            organization_id=organization_id,
            inference_id=inf.id,
            reviewer_user_id=reviewer_user_id,
            decision=decision,
            corrected_output=corrected_output,
            note=note,
            created_at=utcnow(),
        )
    )
    inf.reviewed_by = reviewer_user_id
    if decision == "corrected" and corrected_output:
        merged = dict(inf.output or {})
        merged.update(corrected_output)
        inf.output = merged
        inf.status = AiStatus.succeeded
    elif decision == "confirmed":
        inf.status = AiStatus.succeeded
    elif decision == "rejected":
        inf.status = AiStatus.failed
    await session.flush()
    return inf
