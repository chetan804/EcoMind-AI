"""Version 1 of the REST API (mounted at /api/v1).

Every module router is registered here, and only here. When a module gets its first endpoint:

    from app.modules.waste_reports.router import router as waste_reports_router
    api_v1_router.include_router(
        waste_reports_router, prefix="/waste-reports", tags=["waste-reports"]
    )

Modules are implemented incrementally (docs/project-roadmap.md); see docs/project-completion.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.waste_reports.router import router as waste_reports_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(waste_reports_router, prefix="/waste-reports", tags=["waste-reports"])
