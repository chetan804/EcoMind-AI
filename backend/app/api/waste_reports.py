from fastapi import APIRouter, Depends, HTTPException
import sqlalchemy
from sqlalchemy.orm import Session

from app.core.roles import RoleID
from app.core.security import get_current_user, require_role
from app.db.database import get_db
from app.models.user import User
from app.models.waste_report import WasteReport
from app.schemas.waste_report import (
    WasteReportCreate,
    WasteReportResponse,
)
from app.services.reward_service import award_points


router = APIRouter(
    prefix="/waste-reports",
    tags=["Waste Reports"],
)


@router.post(
    "/",
    response_model=WasteReportResponse,
)
def create_waste_report(
    report_data: WasteReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = WasteReport(
        user_id=current_user.id,
        waste_type=report_data.waste_type,
        description=report_data.description,
        location=report_data.location,
        latitude=report_data.latitude,
        longitude=report_data.longitude,
    )

    db.add(report)
    db.flush()
    award_points(
        db,
        current_user.id,
        "report_submitted",
        f"waste_report:{report.id}",
    )
    db.commit()
    db.refresh(report)

    return report


@router.get(
    "/my-reports",
    response_model=list[WasteReportResponse],
)
def get_my_waste_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = (
        db.query(WasteReport)
        .filter(WasteReport.user_id == current_user.id)
        .order_by(WasteReport.created_at.desc())
        .all()
    )

    return reports


@router.get(
    "/admin/all",
    response_model=list[WasteReportResponse],
)
def get_all_waste_reports(
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    reports = (
        db.query(WasteReport)
        .order_by(WasteReport.created_at.desc())
        .all()
    )

    return reports

@router.patch(
    "/admin/{report_id}/status",
    response_model=WasteReportResponse,
)
def update_report_status(
    report_id: int,
    new_status: str,
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    allowed_statuses = {
        "reported",
        "assigned",
        "collected",
        "resolved",
    }

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Invalid report status",
        )

    report = (
        db.query(WasteReport)
        .filter(WasteReport.id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Waste report not found",
        )

    report.status = new_status

    db.commit()
    db.refresh(report)

    return report