from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.ai_operation import AIOperationLog
from app.models.user import User
from app.models.waste_report import WasteReport
from app.schemas.waste_report import WasteClassificationResponse
from app.ai.inference import inference


router = APIRouter(
    prefix="/classification",
    tags=["AI Classification"],
)


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

    prediction = inference.classify_waste(report.description)

    report.ai_waste_type = prediction.label
    report.ai_confidence = prediction.confidence
    report.ai_model_name = prediction.model_name
    report.ai_model_version = prediction.model_version
    report.ai_provider = prediction.provider
    report.ai_inference_ms = prediction.inference_time_ms
    report.ai_created_at = prediction.created_at
    db.add(
        AIOperationLog(
            user_id=current_user.id,
            operation="waste_classification",
            model_name=prediction.model_name,
            model_version=prediction.model_version,
            provider=prediction.provider,
            input_type="text",
            output_summary=f"category={prediction.label}",
            confidence=prediction.confidence,
            latency_ms=prediction.inference_time_ms,
        )
    )

    db.commit()
    db.refresh(report)

    return WasteClassificationResponse(
        report_id=report.id,
        waste_type=prediction.label,
        confidence=prediction.confidence,
        model_name=prediction.model_name,
        model_version=prediction.model_version,
        provider=prediction.provider,
        inference_time_ms=prediction.inference_time_ms,
    )