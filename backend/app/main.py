"""FastAPI application factory. Run with ``uvicorn app.main:create_app --factory``.

There is deliberately no module-level ``app`` object: importing this module must not require a
valid environment, and tests build apps with explicit settings.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.common.response_schemas import ErrorResponse
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.health.router import router as health_router

API_PREFIX = "/api"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()  # fails fast on invalid configuration
    configure_logging(settings.log_level, json_output=settings.log_json)

    app = FastAPI(
        title="EcoMind AI API",
        version="0.1.0",
        docs_url=None if settings.is_production else f"{API_PREFIX}/v1/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else f"{API_PREFIX}/v1/openapi.json",
        responses={"default": {"model": ErrorResponse}},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router, prefix=API_PREFIX)
    return app
