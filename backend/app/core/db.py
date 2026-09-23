"""Database core: engine, session factory, and the tenant-isolation guard.

Tenant isolation strategy (defence in depth, see docs/adr/0004-tenant-isolation.md):

1. Every tenant-owned table carries a non-null ``organization_id`` FK.
2. While an organization context is active on a session, a ``do_orm_execute``
   hook injects ``organization_id == current_org`` into every ORM SELECT via
   SQLAlchemy's generic ``with_loader_criteria`` (covers lazy loads too).
3. A ``before_flush`` hook refuses tenant-scoped inserts without an
   organization (prevents accidental cross-tenant writes).
4. Write paths (UPDATE/DELETE) require explicit organization predicates in
   services; cross-tenant read *and* write attempts are proven blocked by the
   release-blocking suite in ``tests/test_tenant_isolation.py``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, MetaData, event, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("db")

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )


class TenantScoped:
    """Mixin for tables owned by exactly one organization.

    Models using this mixin MUST be imported before the first query executes
    (guaranteed by ``app/models.py`` importing every domain model).
    """

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )


_TENANT_MODELS: list[type] = []
_checked_registry = False


def _tenant_models() -> list[type]:
    """Discover tenant-scoped mapped classes from the declarative registry."""
    global _checked_registry
    if _checked_registry:
        return _TENANT_MODELS
    for cls in list(Base.registry._class_registry.values()):
        if isinstance(cls, type) and issubclass(cls, TenantScoped) and hasattr(cls, "__tablename__"):
            _TENANT_MODELS.append(cls)
    _checked_registry = True
    return _TENANT_MODELS


def reset_tenant_model_cache() -> None:
    """For test isolation when models are re-imported."""
    global _checked_registry
    _checked_registry = False
    _TENANT_MODELS.clear()


def create_engine(url: str | None = None, **kwargs: Any) -> AsyncEngine:
    from sqlalchemy.pool import NullPool

    return create_async_engine(
        url or settings.database_url,
        echo=settings.sqlalchemy_echo(),
        pool_pre_ping=True,
        # Tests run across multiple event loops; a shared pool would leak
        # connections bound to a previous loop.
        poolclass=NullPool if settings.is_test else None,
        **kwargs,
    )


engine: AsyncEngine = create_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Tenant isolation hooks
# ---------------------------------------------------------------------------


def _apply_tenant_criteria(execute_state) -> None:
    if not execute_state.is_select:
        return
    info = execute_state.session.info
    if info.get("tenant_filter_off") or info.get("org_id") is None:
        return
    org_id = info["org_id"]
    if not _tenant_models():
        return

    from sqlalchemy.orm import with_loader_criteria

    # Root-entity form: applies to every mapped subclass of TenantScoped in
    # the statement (and to lazy loads). Non-tenant entities are unaffected.
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantScoped,
            lambda cls: cls.organization_id == org_id,
            include_aliases=True,
        )
    )


def _guard_flush(session, flush_context, instances) -> None:
    if session.info.get("tenant_filter_off"):
        return
    for obj in session.new:
        if isinstance(obj, TenantScoped) and obj.organization_id is None:
            raise RuntimeError(
                f"Refusing to insert tenant-scoped {type(obj).__name__} without organization_id"
            )


event.listen(Session, "do_orm_execute", _apply_tenant_criteria)
event.listen(Session, "before_flush", _guard_flush)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@contextmanager
def tenant_context(session: AsyncSession, org_id):
    """Activate organization scoping for the duration of the block."""
    info = session.sync_session.info
    prev_org, prev_off = info.get("org_id"), info.get("tenant_filter_off")
    info["org_id"] = org_id
    info["tenant_filter_off"] = False
    try:
        yield session
    finally:
        info["org_id"] = prev_org
        info["tenant_filter_off"] = prev_off


@contextmanager
def unscoped(session: AsyncSession):
    """Explicitly disable the tenant filter — platform-level operations only."""
    info = session.sync_session.info
    prev_off = info.get("tenant_filter_off")
    info["tenant_filter_off"] = True
    try:
        yield session
    finally:
        info["tenant_filter_off"] = prev_off


async def db_ready() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
        return True
    except Exception:
        return False
