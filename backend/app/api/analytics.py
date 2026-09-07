from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.roles import RoleID
from app.core.security import require_role
from app.db.database import get_db
from app.models.user import User
from app.schemas.analytics import DashboardStats, DistributionItem
from app.services.analytics_service import dashboard_stats, waste_distribution


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    return dashboard_stats(db)


@router.get("/waste-distribution", response_model=list[DistributionItem])
def get_waste_distribution(
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    return waste_distribution(db)
