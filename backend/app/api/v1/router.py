"""Version 1 of the REST API (mounted at /api/v1).

Every module router is registered here, and only here. When a module gets its first endpoint,
import its ``router`` and include it with a prefix and tag, as below.

Modules are implemented incrementally (docs/project-roadmap.md); see docs/project-completion.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.anomaly_detection.router import router as anomaly_router
from app.modules.auth.router import router as auth_router
from app.modules.circular_economy.router import router as circular_economy_router
from app.modules.classification.router import router as classification_router
from app.modules.collection.router import router as collection_router
from app.modules.facilities.router import router as facilities_router
from app.modules.fleet.router import router as fleet_router
from app.modules.forecasting.router import router as forecasting_router
from app.modules.material_passports.router import router as passports_router
from app.modules.notifications.router import router as notifications_router
from app.modules.rewards.router import router as rewards_router
from app.modules.route_planning.router import router as route_planning_router
from app.modules.sorting_guide.router import router as sorting_guide_router
from app.modules.waste_reports.router import router as waste_reports_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(waste_reports_router, prefix="/waste-reports", tags=["waste-reports"])
api_v1_router.include_router(facilities_router, prefix="/facilities", tags=["facilities"])
api_v1_router.include_router(
    classification_router, prefix="/classification", tags=["classification"]
)
api_v1_router.include_router(fleet_router, prefix="/fleet", tags=["fleet"])
api_v1_router.include_router(collection_router, prefix="/collection", tags=["collection"])
api_v1_router.include_router(forecasting_router, prefix="/forecasting", tags=["forecasting"])
api_v1_router.include_router(anomaly_router, prefix="/anomalies", tags=["anomalies"])
api_v1_router.include_router(
    route_planning_router, prefix="/route-planning", tags=["route-planning"]
)
api_v1_router.include_router(sorting_guide_router, prefix="/sorting-guide", tags=["sorting-guide"])
api_v1_router.include_router(
    circular_economy_router, prefix="/circular-economy", tags=["circular-economy"]
)
api_v1_router.include_router(
    passports_router, prefix="/material-passports", tags=["material-passports"]
)
api_v1_router.include_router(rewards_router, prefix="/rewards", tags=["rewards"])
api_v1_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
