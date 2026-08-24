from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.waste_report import WasteReport
from app.schemas.waste_report import WasteClassificationResponse
from app.services.waste_classifier import WasteClassifier


router = APIRouter(
    prefix="/classification",
    tags=["AI Classification"],
)


classifier = WasteClassifier()


@router.post(
    "/{report_id}",
    response_model=WasteClassificationResponse,
)
def classify_waste_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = (
        db.query(WasteReport)
        .filter(
            WasteReport.id == report_id,
            WasteReport.user_id == current_user.id,
        )
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Waste report not found",
        )

    predicted_type = classifier.classify(
        report.description
    )

    confidence = 0.85

    report.ai_waste_type = predicted_type
    report.ai_confidence = confidence

    db.commit()
    db.refresh(report)

    return WasteClassificationResponse(
        report_id=report.id,
        waste_type=predicted_type,
        confidence=confidence,
    )