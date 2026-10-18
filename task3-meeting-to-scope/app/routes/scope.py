"""Scope generation, versioning, change detection, and approval endpoints."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.database import Database
from app.dependencies import (
    get_approval_service,
    get_database,
    get_estimation_service,
    get_feasibility_service,
    get_requirements_service,
    get_scope_diff_service,
    get_transcript_service,
)
from app.schemas import (
    ApprovalRequest,
    ApprovalResponse,
    MilestoneItem,
    ScopeDiffReport,
    ScopeDocument,
    ScopeStatus,
)
from app.services.approval_service import ApprovalService
from app.services.estimation_service import EstimationService
from app.services.feasibility_service import FeasibilityService
from app.services.requirements_service import RequirementsService
from app.services.scope_diff_service import ScopeDiffService
from app.services.transcript_service import TranscriptService

router = APIRouter(prefix="/api/v1/scope", tags=["scope"])


class GenerateScopeRequest(BaseModel):
    """Request payload to analyze transcript and generate scope."""

    transcript_id: str
    project_name: str | None = None
    client_name: str | None = None


class ScopeDiffRequest(BaseModel):
    """Request payload to compare new transcript or change request against existing scope."""

    new_transcript_id: str | None = None
    change_request_text: str | None = None


@router.post("/generate", response_model=ScopeDocument, status_code=status.HTTP_201_CREATED)
async def generate_scope(
    payload: GenerateScopeRequest,
    transcript_service: TranscriptService = Depends(get_transcript_service),
    requirements_service: RequirementsService = Depends(get_requirements_service),
    feasibility_service: FeasibilityService = Depends(get_feasibility_service),
    estimation_service: EstimationService = Depends(get_estimation_service),
    database: Database = Depends(get_database),
):
    """End-to-end pipeline: transcript -> requirements -> feasibility -> estimates -> scope draft."""
    transcript = transcript_service.get_transcript(payload.transcript_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcript not found: {payload.transcript_id}",
        )

    # 1. Requirements Extraction
    requirements, out_of_scope, open_questions = await requirements_service.extract(
        transcript.content
    )

    # 2. Grounded Feasibility via Task 1 Knowledge Brain
    feasibility_list = await feasibility_service.evaluate(requirements)

    # 3. Transparent Effort Estimates
    estimates, estimate_summary = await estimation_service.generate_estimates(
        requirements, feasibility_list
    )

    now = datetime.now(timezone.utc).isoformat()
    scope_id = f"scope_{uuid.uuid4().hex[:10]}"
    project_name = payload.project_name or transcript.metadata.project_name or "Directory Solution Project"
    client_name = payload.client_name or transcript.metadata.client_name or "Valued Client"

    # 4. Generate structured milestones based on estimate packages
    phase1_hours = round(estimate_summary.total_hours_base * 0.4, 1)
    phase2_hours = round(estimate_summary.total_hours_base * 0.4, 1)
    phase3_hours = round(estimate_summary.total_hours_base - phase1_hours - phase2_hours, 1)

    milestones = [
        MilestoneItem(
            milestone_id="M1",
            name="Milestone 1: Core Configuration & Taxonomy",
            deliverables=["Search forms", "Category structure", "General settings"],
            estimated_hours=phase1_hours,
        ),
        MilestoneItem(
            milestone_id="M2",
            name="Milestone 2: Integrations & Workflows",
            deliverables=["Payment setup", "Lead auto-matching", "Data migration"],
            estimated_hours=phase2_hours,
            dependencies=["M1"],
        ),
        MilestoneItem(
            milestone_id="M3",
            name="Milestone 3: Verification & Go-Live",
            deliverables=["Performance verification", "User testing", "Domain launch"],
            estimated_hours=phase3_hours,
            dependencies=["M2"],
        ),
    ]

    summary = (
        f"Initial project scope for {client_name} ({project_name}) derived from meeting discovery. "
        f"Includes {len(requirements)} extracted requirements with an estimated base effort of {estimate_summary.total_hours_base} hours."
    )

    scope = ScopeDocument(
        scope_id=scope_id,
        version=1,
        transcript_id=transcript.transcript_id,
        project_name=project_name,
        client_name=client_name,
        summary=summary,
        business_objectives=[
            "Launch a compliant, high-performing member directory.",
            "Automate membership registration and payment processing.",
        ],
        requirements=requirements,
        feasibility_analysis=feasibility_list,
        estimates=estimates,
        estimate_summary=estimate_summary,
        out_of_scope=out_of_scope,
        open_questions=open_questions,
        milestones=milestones,
        status=ScopeStatus.PENDING_REVIEW,
        created_at=now,
        updated_at=now,
    )

    database.save_scope(scope)
    return scope


@router.get("/{scope_id}", response_model=ScopeDocument)
def get_scope(
    scope_id: str,
    database: Database = Depends(get_database),
):
    """Retrieve saved scope document by ID."""
    scope = database.get_scope(scope_id)
    if not scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scope not found: {scope_id}",
        )
    return scope


@router.post("/{scope_id}/approve", response_model=ApprovalResponse)
def approve_scope(
    scope_id: str,
    payload: ApprovalRequest,
    approval_service: ApprovalService = Depends(get_approval_service),
):
    """Approve a draft or pending scope."""
    try:
        return approval_service.approve_scope(scope_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{scope_id}/reject", response_model=ApprovalResponse)
def reject_scope(
    scope_id: str,
    payload: ApprovalRequest,
    approval_service: ApprovalService = Depends(get_approval_service),
):
    """Reject a draft scope."""
    try:
        return approval_service.reject_scope(scope_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{scope_id}/diff", response_model=ScopeDiffReport)
async def generate_scope_diff(
    scope_id: str,
    payload: ScopeDiffRequest,
    database: Database = Depends(get_database),
    transcript_service: TranscriptService = Depends(get_transcript_service),
    requirements_service: RequirementsService = Depends(get_requirements_service),
    estimation_service: EstimationService = Depends(get_estimation_service),
    scope_diff_service: ScopeDiffService = Depends(get_scope_diff_service),
):
    """Compare a new transcript or change request against an existing scope."""
    base_scope = database.get_scope(scope_id)
    if not base_scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Base scope not found: {scope_id}",
        )

    text_to_compare = ""
    if payload.new_transcript_id:
        new_tr = transcript_service.get_transcript(payload.new_transcript_id)
        if not new_tr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"New transcript not found: {payload.new_transcript_id}",
            )
        text_to_compare = new_tr.content
    elif payload.change_request_text:
        text_to_compare = payload.change_request_text
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'new_transcript_id' or 'change_request_text'.",
        )

    new_requirements, _, _ = await requirements_service.extract(text_to_compare)
    new_estimates, _ = await estimation_service.generate_estimates(new_requirements)

    diff_report = scope_diff_service.compare_scopes(
        base_scope=base_scope,
        new_requirements=new_requirements,
        new_estimates=new_estimates,
        transcript_text=text_to_compare,
    )

    return diff_report


@router.post("/{scope_id}/revisions/{diff_id}/approve", response_model=ApprovalResponse)
def approve_scope_revision(
    scope_id: str,
    diff_id: str,
    payload: ApprovalRequest,
    approval_service: ApprovalService = Depends(get_approval_service),
):
    """Approve a scope change report, superseding base scope and creating an approved vN+1 version."""
    try:
        return approval_service.approve_revision(
            base_scope_id=scope_id,
            diff_id=diff_id,
            request=payload,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
