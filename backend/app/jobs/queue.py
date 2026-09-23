"""PostgreSQL-backed job queue with SKIP LOCKED claiming.

Handlers are registered by name. The embedded worker (dev) and the standalone
worker process (production) share this code path.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta

from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.db import SessionLocal, tenant_context, utcnow
from app.core.logging import get_logger
from app.jobs.models import Job, JobStatus

log = get_logger("jobs")

HANDLERS: dict[str, Callable[..., Awaitable]] = {}


def register(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn

    return deco


async def enqueue(
    session, *, kind: str, payload: dict | None = None, organization_id: uuid.UUID | None = None,
    run_after=None, priority: int = 0, max_attempts: int = 3,
) -> Job:
    job = Job(
        organization_id=organization_id,
        kind=kind,
        payload=payload or {},
        status=JobStatus.queued,
        priority=priority,
        run_after=run_after or utcnow(),
        max_attempts=max_attempts,
    )
    session.add(job)
    await session.flush()
    log.info("job_enqueued", kind=kind, job_id=str(job.id))
    return job


async def claim_next(session) -> Job | None:
    """Atomically claim one runnable job (SELECT ... FOR UPDATE SKIP LOCKED)."""
    now = utcnow()
    q = (
        select(Job)
        .where(Job.status == JobStatus.queued, Job.run_after <= now)
        .order_by(Job.priority.desc(), Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = (await session.execute(q)).scalar_one_or_none()
    if job is None:
        return None
    job.status = JobStatus.running
    job.locked_by = f"worker-{uuid.uuid4().hex[:8]}"
    job.locked_at = now
    job.attempts += 1
    await session.flush()
    return job


async def run_job(job: Job) -> None:
    handler = HANDLERS.get(job.kind)
    started = time.perf_counter()
    try:
        if handler is None:
            raise RuntimeError(f"No handler for job kind '{job.kind}'")
        async with SessionLocal() as session:
            if job.organization_id:
                with tenant_context(session, job.organization_id):
                    await handler(session, job.payload, job.organization_id)
            else:
                await handler(session, job.payload, None)
            # reflect terminal state on the same row via fresh session
        await _finish(job.id, JobStatus.succeeded, duration_ms=(time.perf_counter() - started) * 1000)
    except Exception as e:
        log.error("job_failed", kind=job.kind, job_id=str(job.id), error=repr(e)[:500])
        retry = job.attempts < job.max_attempts
        await _finish(
            job.id,
            JobStatus.queued if retry else JobStatus.failed,
            error=str(e)[:2000],
            retry_in=timedelta(seconds=10 * job.attempts) if retry else None,
        )


async def _finish(job_id, status: JobStatus, *, error: str | None = None, duration_ms: float | None = None, retry_in=None) -> None:
    async with SessionLocal() as session:
        values = {"status": status}
        if error is not None:
            values["last_error"] = error
        if duration_ms is not None:
            values["duration_ms"] = duration_ms
            values["finished_at"] = utcnow()
        if retry_in is not None:
            values["run_after"] = utcnow() + retry_in
        await session.execute(update(Job).where(Job.id == job_id).values(**values))
        await session.commit()


async def worker_loop(stop_after: float | None = None) -> None:
    """Poll-claim-execute loop. Runs embedded in dev and as `python -m app.jobs.worker` in prod."""
    from app.core.logging import configure_logging

    configure_logging(settings.log_level)
    log.info("worker_started", poll_seconds=settings.worker_poll_seconds)
    started = time.monotonic()
    idle_cycles = 0
    while True:
        if stop_after is not None and time.monotonic() - started > stop_after:
            return
        claimed = False
        async with SessionLocal() as session:
            job = await claim_next(session)
            if job is not None:
                await session.commit()
                claimed = True
        if claimed:
            job_obj = job  # claimed in this loop iteration
            await run_job(job_obj)
            idle_cycles = 0
        else:
            idle_cycles += 1
            await asyncio_sleep(settings.worker_poll_seconds if idle_cycles < 5 else min(5.0, settings.worker_poll_seconds * 5))


async def asyncio_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


async def requeue_stale_jobs(older_than_minutes: int = 30) -> int:
    """Crash recovery: jobs running longer than the threshold go back to queued."""
    cutoff = utcnow() - timedelta(minutes=older_than_minutes)
    async with SessionLocal() as session:
        result = await session.execute(
            update(Job)
            .where(Job.status == JobStatus.running, Job.locked_at < cutoff)
            .values(status=JobStatus.queued, locked_by=None, locked_at=None)
        )
        await session.commit()
        return result.rowcount or 0
