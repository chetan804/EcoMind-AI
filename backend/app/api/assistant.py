from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.assistant import FallbackAssistant
from app.db.database import get_db
from app.models.user import User
from app.models.waste_report import WasteReport
from app.schemas.assistant import AssistantRequest, AssistantResponse
from app.core.security import get_current_user


router = APIRouter(prefix="/assistant", tags=["EcoMind AI Assistant"])
assistant = FallbackAssistant()


@router.post("/ask", response_model=AssistantResponse)
def ask_assistant(
    request: AssistantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report_count = (
        db.query(WasteReport)
        .filter(WasteReport.user_id == current_user.id)
        .count()
    )
    response = assistant.answer(
        request.prompt,
        {"report_count": report_count, "role_id": current_user.role_id},
    )
    return AssistantResponse(
        answer=response.answer,
        provider=response.provider,
        model_name=response.model_name,
        is_fallback=response.is_fallback,
    )
