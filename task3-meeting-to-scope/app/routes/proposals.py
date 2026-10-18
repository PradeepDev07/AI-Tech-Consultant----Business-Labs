"""Client proposal generation endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from app.database import Database
from app.dependencies import get_database, get_proposal_service
from app.schemas import ProposalResponse
from app.services.proposal_service import ProposalService

router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])


@router.get("/{scope_id}", response_model=ProposalResponse)
def get_proposal_for_scope(
    scope_id: str,
    database: Database = Depends(get_database),
    proposal_service: ProposalService = Depends(get_proposal_service),
):
    """Generate and retrieve a client proposal derived directly from a validated scope document."""
    scope = database.get_scope(scope_id)
    if not scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scope not found: {scope_id}",
        )

    return proposal_service.generate_proposal(scope)
