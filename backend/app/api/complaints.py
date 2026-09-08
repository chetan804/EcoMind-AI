import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.complaint_analyzer import KeywordComplaintAnalyzer
from app.models.ai_operation import AIOperationLog
from app.core.roles import RoleID
from app.core.security import get_current_user, require_role
from app.db.database import get_db
from app.models.complaint import Complaint, ComplaintStatusHistory
from app.models.notification import Notification
from app.models.user import User
from app.models.waste_report import WasteReport
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintResponse,
    ComplaintStatusUpdate,
)
from app.services.complaint_service import change_complaint_status
from app.services.notification_service import create_notification


router = APIRouter(prefix="/complaints", tags=["Complaints"])
complaint_analyzer = KeywordComplaintAnalyzer()


@router.post("/", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
def create_complaint(
    complaint_data: ComplaintCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if complaint_data.report_id is not None:
        report = (
            db.query(WasteReport)
            .filter(
                WasteReport.id == complaint_data.report_id,
                WasteReport.user_id == current_user.id,
            )
            .first()
        )
        if report is None:
            raise HTTPException(status_code=404, detail="Waste report not found")

    analysis = complaint_analyzer.analyze(
        complaint_data.title,
        complaint_data.description,
    )
    complaint = Complaint(
        user_id=current_user.id,
        report_id=complaint_data.report_id,
        title=complaint_data.title,
        description=complaint_data.description,
        location=complaint_data.location,
        latitude=complaint_data.latitude,
        longitude=complaint_data.longitude,
        status="submitted",
        ai_category=analysis.category,
        ai_priority=analysis.priority,
        ai_keywords=json.dumps(analysis.keywords),
        ai_confidence=analysis.confidence,
        ai_model_name=analysis.model_name,
        ai_model_version=analysis.model_version,
        ai_created_at=analysis.created_at,
    )
    complaint.history.append(
        ComplaintStatusHistory(
            changed_by=current_user.id,
            new_status="submitted",
            note="Complaint submitted",
        )
    )
    db.add(complaint)
    db.add(
        AIOperationLog(
            user_id=current_user.id,
            operation="complaint_analysis",
            model_name=analysis.model_name,
            model_version=analysis.model_version,
            provider=analysis.provider,
            input_type="text",
            output_summary=(
                f"category={analysis.category};priority={analysis.priority}"
            ),
            confidence=analysis.confidence,
            latency_ms=analysis.inference_time_ms,
        )
    )
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("/my", response_model=list[ComplaintResponse])
def get_my_complaints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Complaint)
        .filter(Complaint.user_id == current_user.id)
        .order_by(Complaint.created_at.desc())
        .all()
    )


@router.get("/admin/all", response_model=list[ComplaintResponse])
def get_all_complaints(
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    return db.query(Complaint).order_by(Complaint.created_at.desc()).all()


@router.patch("/admin/{complaint_id}", response_model=ComplaintResponse)
def update_complaint(
    complaint_id: int,
    update_data: ComplaintStatusUpdate,
    current_user: User = Depends(require_role(RoleID.ADMIN)),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if update_data.assigned_to is not None:
        assignee = (
            db.query(User)
            .filter(
                User.id == update_data.assigned_to,
                User.role_id == int(RoleID.COLLECTOR),
                User.is_active.is_(True),
            )
            .first()
        )
        if assignee is None:
            raise HTTPException(status_code=400, detail="Invalid collector")
        complaint.assigned_to = assignee.id

    try:
        history = change_complaint_status(
            complaint,
            update_data.status,
            current_user.id,
            update_data.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if update_data.resolution is not None:
        complaint.resolution = update_data.resolution
    complaint.history.append(history)
    db.add(
        create_notification(
            user_id=complaint.user_id,
            event_type="complaint_status_changed",
            title="Complaint status updated",
            message=f"Your complaint is now {complaint.status}.",
        )
    )
    db.commit()
    db.refresh(complaint)
    return complaint
