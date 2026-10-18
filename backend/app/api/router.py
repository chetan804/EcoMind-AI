"""Top-level API router: mounts each API version under its prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.router import api_v1_router

api_router = APIRouter()
api_router.include_router(api_v1_router, prefix="/v1")
