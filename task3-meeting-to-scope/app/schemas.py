"""Pydantic v2 domain schemas for Task 3 Meeting to Scope Agent."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator


# ==========================================
# Citations & Evidence (Task 1 Compatible)
# ==========================================
class Citation(BaseModel):
    """Authoritative citation from Task 1 Knowledge Brain."""

    article_id: str
    article_title: str
    source_url: str
    heading: str | None = None
    chunk_index: int | None = None
    excerpt: str
    relevance_score: float | None = None


# ==========================================
# Transcripts
# ==========================================
class TranscriptMetadata(BaseModel):
    """Metadata describing a meeting transcript."""

    project_name: str | None = None
    client_name: str | None = None
    meeting_date: str | None = None
    participants: list[str] = Field(default_factory=list)


class TranscriptCreate(BaseModel):
    """Inbound request to ingest a meeting transcript."""

    transcript_text: str = Field(
        default="",
        description="Raw meeting transcript text",
    )
    metadata: TranscriptMetadata = Field(default_factory=TranscriptMetadata)

    @model_validator(mode="before")
    @classmethod
    def resolve_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            text = (
                data.get("transcript_text")
                or data.get("content")
                or data.get("text")
                or ""
            )
            data["transcript_text"] = str(text).strip()

            meta = data.get("metadata")
            if not isinstance(meta, dict):
                meta = {}
            if "title" in data and "project_name" not in meta:
                meta["project_name"] = data["title"]
            if "project_name" in data and "project_name" not in meta:
                meta["project_name"] = data["project_name"]
            if "client_name" in data and "client_name" not in meta:
                meta["client_name"] = data["client_name"]
            data["metadata"] = meta
        return data


class TranscriptResponse(BaseModel):
    """Persisted transcript record."""

    transcript_id: str
    content: str
    metadata: TranscriptMetadata
    char_count: int
    created_at: str


# ==========================================
# Requirements Extraction
# ==========================================
class RequirementCategory(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    ROLES_AND_PERMISSIONS = "roles_and_permissions"
    INTEGRATIONS = "integrations"
    DATA = "data"
    SECURITY_AND_PRIVACY = "security_and_privacy"
    PERFORMANCE = "performance"
    EXCLUSION = "exclusion"


class RequirementStatus(str, Enum):
    CONFIRMED = "confirmed"
    ASSUMED = "assumed"
    AMBIGUOUS = "ambiguous"
    REQUIRES_CLARIFICATION = "requires_clarification"


class RequirementPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNSPECIFIED = "unspecified"


class RequirementItem(BaseModel):
    """Structured, traceable requirement extracted from meeting transcript."""

    id: str = Field(..., description="Stable requirement identifier, e.g. REQ-001")
    category: RequirementCategory
    title: str
    description: str
    source_quote: str = Field(
        ..., description="Exact or verbatim quotation from transcript proving provenance"
    )
    status: RequirementStatus
    priority: RequirementPriority = RequirementPriority.UNSPECIFIED
    acceptance_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


# ==========================================
# Feasibility Analysis (Task 1 Grounded)
# ==========================================
class FeasibilityCategory(str, Enum):
    SUPPORTED_BY_EVIDENCE = "supported_by_evidence"
    POTENTIALLY_FEASIBLE = "potentially_feasible"
    BLOCKED_BY_DEPENDENCY = "blocked_by_dependency"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    REQUIRES_CLARIFICATION = "requires_clarification"


class RequirementFeasibility(BaseModel):
    """Grounding evaluation of a requirement against Task 1 Solution Center evidence."""

    requirement_id: str
    feasibility_status: FeasibilityCategory
    findings: str
    evidence_citations: list[Citation] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    technical_notes: str = ""
    is_supported: bool = False


# ==========================================
# Estimation Engine
# ==========================================
class EstimateItem(BaseModel):
    """Work package estimate item with transparent uncertainty."""

    requirement_id: str
    task_description: str
    hours_low: float = Field(..., ge=0.0)
    hours_base: float = Field(..., ge=0.0)
    hours_high: float = Field(..., ge=0.0)
    confidence_range: str = "medium"
    assumptions: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    requires_validation: bool = False


class EstimateSummary(BaseModel):
    """Mathematically verified sum totals for effort estimates."""

    total_hours_low: float
    total_hours_base: float
    total_hours_high: float
    currency_rate_status: str = "unpriced_rates_unknown"
    notes: str = "Estimates reflect preliminary engineering effort. Commercial rates and staffing require human sales review."


# ==========================================
# Scope Document & Proposal
# ==========================================
class ScopeStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class MilestoneItem(BaseModel):
    """Project milestone phase."""

    milestone_id: str
    name: str
    deliverables: list[str]
    estimated_hours: float
    dependencies: list[str] = Field(default_factory=list)


class ScopeDocument(BaseModel):
    """Complete, versioned project scope specification."""

    scope_id: str
    version: int = 1
    transcript_id: str
    project_name: str
    client_name: str
    summary: str
    business_objectives: list[str] = Field(default_factory=list)
    requirements: list[RequirementItem] = Field(default_factory=list)
    feasibility_analysis: list[RequirementFeasibility] = Field(default_factory=list)
    estimates: list[EstimateItem] = Field(default_factory=list)
    estimate_summary: EstimateSummary
    out_of_scope: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    milestones: list[MilestoneItem] = Field(default_factory=list)
    status: ScopeStatus = ScopeStatus.DRAFT
    approved_by: str | None = None
    approved_at: str | None = None
    previous_version_id: str | None = None
    created_at: str
    updated_at: str


class ProposalResponse(BaseModel):
    """Client proposal derived consistently from the validated scope object."""

    proposal_id: str
    scope_id: str
    version: int
    client_name: str
    project_name: str
    executive_summary: str
    deliverables: list[str]
    out_of_scope: list[str]
    technical_assumptions: list[str]
    risk_mitigations: list[str]
    milestones: list[MilestoneItem]
    effort_summary: EstimateSummary
    approval_status: ScopeStatus
    disclaimer: str = "Preliminary proposal derived from initial discovery transcript. Subject to formal human sign-off."


# ==========================================
# Scope Difference Detection
# ==========================================
class DiffChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"
    CONTRADICTION = "contradiction"


class RequirementDiff(BaseModel):
    """Granular comparison of an individual requirement across scope versions."""

    requirement_id: str
    change_type: DiffChangeType
    title: str
    previous_value: str | None = None
    new_value: str | None = None
    reason_and_quote: str
    effort_impact_hours: float = 0.0
    risk_impact: str = "none"
    clarification_needed: bool = False


class ScopeDiffReport(BaseModel):
    """Structured scope delta report comparing a new transcript against existing scope."""

    diff_id: str
    base_scope_id: str
    base_version: int
    proposed_version: int
    diff_summary: str
    requirement_changes: list[RequirementDiff]
    total_hours_delta_base: float
    has_contradictions: bool
    requires_human_approval: bool = True
    created_at: str


# ==========================================
# Human Review & Approvals
# ==========================================
class ApprovalAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class ApprovalRequest(BaseModel):
    """Reviewer decision payload."""

    action: ApprovalAction = ApprovalAction.APPROVE
    reviewer_name: str = Field(default="lead_architect", min_length=2)
    reviewer_notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "action" not in data:
                data["action"] = "approve"
            if "reviewer_name" not in data:
                data["reviewer_name"] = (
                    data.get("approved_by")
                    or data.get("reviewer")
                    or "lead_architect"
                )
            if "reviewer_notes" not in data:
                data["reviewer_notes"] = data.get("approval_notes") or data.get("notes")
        return data


class ApprovalResponse(BaseModel):
    """Outcome of an approval or rejection operation."""

    scope_id: str
    version: int
    status: ScopeStatus
    action: ApprovalAction
    reviewed_by: str
    timestamp: str
    message: str
    new_version_created: bool = False
    new_scope_id: str | None = None
