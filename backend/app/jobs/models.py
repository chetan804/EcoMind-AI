"""PostgreSQL-backed job queue.

Jobs are rows with ``FOR UPDATE SKIP LOCKED`` claiming: transactional with the
application database, crash-safe, and horizontally scalable by running more
worker processes. The embedded asyncio worker runs inside the API for
development; production runs ``python -m app.jobs.worker`` as a separate
process (see docs/adr/0007-background-jobs-and-limits.md for the Redis/ARQ
scale-out path when sub-second scheduling latency matters).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDMixin


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class Job(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, native_enum=False, length=16), default=JobStatus.queued, nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # higher runs first
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_by: Mapped[str | None] = mapped_column(String(64))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float | None] = mapped_column(Float)
