"""EcoMind-AI API application."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — load all models for metadata + tenant registry
from app.admin.router import router as admin_router
from app.ai.router import router as ai_router
from app.analytics.router import router as analytics_router
from app.auth.rbac import seed_rbac
from app.auth.router import router as auth_router
from app.collection.router import router as collection_router
from app.complaints.router import router as complaints_router
from app.core.config import settings
from app.core.db import SessionLocal, db_ready
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, new_request_id, request_id_var
from app.core.rate_limit import client_ip
from app.fleet.router import router as fleet_router
from app.iot.router import ingest_router, router as iot_router
from app.media.router import router as media_router
from app.notifications.router import router as notifications_router
from app.orgs.router import router as orgs_router
from app.rewards.router import router as rewards_router
from app.routing.router import router as routing_router
from app.sustainability.router import router as sustainability_router
from app.users.router import router as users_router
from app.waste.router import router as waste_router

configure_logging(settings.log_level)

API_PREFIX = settings.api_prefix

_started_at = time.monotonic()


async def _startup_init() -> None:
    """Seed RBAC (idempotent) once the database is reachable."""
    try:
        async with SessionLocal() as session:
            await seed_rbac(session)
    except Exception as e:  # database not migrated yet — health endpoints will report
        from app.core.logging import get_logger

        get_logger("startup").warning("rbac_seed_skipped", error=str(e)[:200])


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = None
    await _startup_init()
    if settings.run_embedded_worker and not settings.is_test:
        import asyncio

        import app.jobs.handlers  # noqa: F401

        from app.jobs.queue import worker_loop

        worker_task = asyncio.create_task(worker_loop())
    yield
    if worker_task is not None:
        worker_task.cancel()


app = FastAPI(
    title=settings.project_name,
    version="2.0.0",
    description=(
        "Multi-tenant smart waste management & environmental intelligence platform. "
        "All endpoints are versioned under /api/v1 and authorization is permission-based."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = new_request_id()
    request_id_var.set(rid)
    request.state.request_id = rid
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-Id"] = rid
    from app.core.logging import get_logger

    get_logger("http").info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 1),
        user=str(getattr(request.state, "user_id", "") or ""),
        ip=client_ip(request),
    )
    return response


install_error_handlers(app)

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(orgs_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(waste_router, prefix=API_PREFIX)
app.include_router(complaints_router, prefix=API_PREFIX)
app.include_router(collection_router, prefix=API_PREFIX)
app.include_router(fleet_router, prefix=API_PREFIX)
app.include_router(routing_router, prefix=API_PREFIX)
app.include_router(iot_router, prefix=API_PREFIX)
app.include_router(ingest_router, prefix=API_PREFIX)
app.include_router(ai_router, prefix=API_PREFIX)
app.include_router(media_router, prefix=API_PREFIX)
app.include_router(sustainability_router, prefix=API_PREFIX)
app.include_router(analytics_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=API_PREFIX)
app.include_router(rewards_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)


@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "service": "ecomind-ai-api",
        "version": "2.0.0",
        "uptime_s": round(time.monotonic() - _started_at, 1),
    }


@app.get("/ready", tags=["system"])
async def readiness():
    db = await db_ready()
    return {
        "status": "ready" if db else "degraded",
        "checks": {"database": "up" if db else "down"},
    }
