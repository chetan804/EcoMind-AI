"""Standalone worker entrypoint: `python -m app.jobs.worker`."""

from __future__ import annotations

import asyncio

from app.jobs.queue import requeue_stale_jobs, worker_loop


async def main() -> None:
    import app.jobs.handlers  # noqa: F401 — register handlers

    recovered = await requeue_stale_jobs()
    if recovered:
        print(f"recovered {recovered} stale job(s)")
    await worker_loop()


if __name__ == "__main__":
    asyncio.run(main())
