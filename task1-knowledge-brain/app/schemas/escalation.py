"""Schemas for human escalation, expert answers, and approval workflow."""

from datetime import datetime
from enum import Enum
import uuid
from pydantic import BaseModel, Field


class EscalationStatus(str, Enum):
    """Lifecycle statuses for an escalation record."""

    OPEN = "open"
    ANSWERED = "answered"
    APPROVED = "approved"
    REJECTED = "rejected"


class EscalationCreate(BaseModel):
    """Payload to create a new human escalation record."""

    question: str = Field(..., min_length=2, max_length=1000)
    retrieved_evidence: list[dict] = Field(default_factory=list)
    user_context: dict | None = None


class EscalationAnswerRequest(BaseModel):
    """Payload for human expert answering an escalated question."""

    expert_answer: str = Field(..., min_length=5)
    expert_name: str = Field(default="Human Expert")


class EscalationApproveRequest(BaseModel):
    """Payload to approve an expert answer and trigger knowledge reindexing."""

    reviewer_notes: str | None = None
    approved_by: str = Field(default="Knowledge Admin")


class EscalationResponse(BaseModel):
    """Full escalation record with status and audit trail."""

    escalation_id: str
    question: str
    status: EscalationStatus
    retrieved_evidence: list[dict] = Field(default_factory=list)
    expert_answer: str | None = None
    expert_name: str | None = None
    answered_at: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    reindexed_at: str | None = None
    created_at: str
    updated_at: str
    audit_trail: list[str] = Field(default_factory=list)


class EscalationListResponse(BaseModel):
    """List response of escalation records."""

    total: int
    escalations: list[EscalationResponse]
