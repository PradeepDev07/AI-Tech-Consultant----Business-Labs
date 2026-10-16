"""Question answering API endpoints."""

from fastapi import APIRouter, Depends
from app.dependencies import get_answer_service
from app.schemas.questions import QuestionRequest, QuestionResponse
from app.services.answer_service import AnswerService

router = APIRouter(prefix="/api/v1/questions", tags=["questions"])


@router.post("", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    answer_service: AnswerService = Depends(get_answer_service),
):
    """Answer natural language question with citations to authoritative help center articles."""
    return answer_service.answer_question(request)
