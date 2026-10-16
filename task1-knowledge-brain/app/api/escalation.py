"""Escalation API endpoints for human expert knowledge integration."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.exceptions import EscalationNotFoundError, StorageError
from app.dependencies import get_escalation_service, verify_api_token
from app.schemas.escalation import (
    EscalationAnswerRequest,
    EscalationApproveRequest,
    EscalationCreate,
    EscalationListResponse,
    EscalationResponse,
    EscalationStatus,
)
from app.services.escalation_service import EscalationService

router = APIRouter(prefix="/api/v1/escalations", tags=["escalations"])


@router.post("", response_model=EscalationResponse, status_code=status.HTTP_201_CREATED)
async def create_escalation(
    payload: EscalationCreate,
    service: EscalationService = Depends(get_escalation_service),
):
    """Create a new human escalation for an unanswered or ambiguous question."""
    return service.create_escalation(
        question=payload.question,
        retrieved_evidence=payload.retrieved_evidence,
        context=payload.user_context,
    )


@router.get("", response_model=EscalationListResponse)
async def list_escalations(
    status_filter: EscalationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: EscalationService = Depends(get_escalation_service),
):
    """Retrieve list of escalations filtered by status."""
    return service.list_escalations(
        status=status_filter, limit=limit, offset=offset
    )


@router.post("/{escalation_id}/answer", response_model=EscalationResponse)
async def answer_escalation(
    escalation_id: str,
    payload: EscalationAnswerRequest,
    service: EscalationService = Depends(get_escalation_service),
    _auth: None = Depends(verify_api_token),
):
    """Allow a human expert to provide an authoritative answer to an escalation."""
    try:
        return service.answer_escalation(
            escalation_id=escalation_id,
            expert_answer=payload.expert_answer,
            expert_name=payload.expert_name,
        )
    except EscalationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{escalation_id}/approve", response_model=EscalationResponse)
async def approve_escalation(
    escalation_id: str,
    payload: EscalationApproveRequest,
    service: EscalationService = Depends(get_escalation_service),
    _auth: None = Depends(verify_api_token),
):
    """Approve an answered escalation, triggering knowledge base re-indexing."""
    try:
        return service.approve_escalation(
            escalation_id=escalation_id,
            approved_by=payload.approved_by,
            reviewer_notes=payload.reviewer_notes,
        )
    except EscalationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except StorageError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
