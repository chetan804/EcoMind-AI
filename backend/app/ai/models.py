"""AI inferences and the human-review trail.

Every inference records provider, model, structured output, confidence and
latency. Low-confidence or failed items route to the human-review queue —
model output is never treated as authoritative just because it parses.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped, TimestampMixin, UUIDMixin


class AiTask(str, enum.Enum):
    waste_classification = "waste_classification"
    complaint_classification = "complaint_classification"
    complaint_summarization = "complaint_summarization"
    anomaly_detection = "anomaly_detection"
    demand_forecast = "demand_forecast"
    assistant = "assistant"


class AiStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    needs_review = "needs_review"


class AiInference(UUIDMixin, TimestampMixin, TenantScoped, Base):
    __tablename__ = "ai_inferences"

    task: Mapped[AiTask] = mapped_column(
        SAEnum(AiTask, native_enum=False, length=32), nullable=False, index=True
    )
    status: Mapped[AiStatus] = mapped_column(
        SAEnum(AiStatus, native_enum=False, length=16), default=AiStatus.pending, nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    model: Mapped[str] = mapped_column(String(96), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(48))
    input_type: Mapped[str] = mapped_column(String(16), nullable=False)  # image | text
    input_ref: Mapped[uuid.UUID | None] = mapped_column()  # logical reference (report/complaint id)
    input_summary: Mapped[str | None] = mapped_column(Text)
    media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))
    output: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    # Simulated inferences (demo seed data) are flagged and surfaced as such.
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (Index("ix_ai_inferences_org_task", "organization_id", "task"),)


class AiReview(UUIDMixin, Base):
    __tablename__ = "ai_reviews"

    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    inference_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_inferences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # confirmed | corrected | rejected
    corrected_output: Mapped[dict | None] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
