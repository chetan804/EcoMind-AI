"""Engine and session management (synchronous SQLAlchemy 2.x with the psycopg v3 driver).

Transactions are owned by services: a service opens a unit of work, calls repositories, and
commits once. Repositories never commit.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[Session]:
    """FastAPI dependency yielding one session per request.

    Deliberately ``async``: a synchronous generator dependency is created AND closed on the request
    thread pool, so closing needs a free thread. Under load every thread can be waiting for a
    connection that a finished request still holds while it waits for a thread to close its
    session; the process then stalls until the pool timeout (reproduced with 100 concurrent users,
    see docs/testing/load-test-report.md). Creating a session does no I/O, and closing one only
    returns an idle connection to the pool (a rollback round trip), so both are done on the event
    loop and never wait for a thread. Handlers stay synchronous and run on the thread pool.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
