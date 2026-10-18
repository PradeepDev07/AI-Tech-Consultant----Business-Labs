"""Unit tests for ProposalAgent."""

from agents.proposal_agent import ProposalAgent
from app.schemas import (
    EstimateSummary,
    RequirementCategory,
    RequirementItem,
    RequirementStatus,
    ScopeDocument,
    ScopeStatus,
)


def test_proposal_derived_from_scope_without_contradiction():
    agent = ProposalAgent()

    reqs = [
        RequirementItem(
            id="REQ-001",
            category=RequirementCategory.FUNCTIONAL,
            title="Member Directory",
            description="Search directory",
            source_quote="quote",
            status=RequirementStatus.CONFIRMED,
        )
    ]
    scope = ScopeDocument(
        scope_id="scope_test_123",
        version=1,
        transcript_id="tr_123",
        project_name="Coastal Directory",
        client_name="Coastal Chamber",
        summary="Test scope summary",
        requirements=reqs,
        estimates=[],
        estimate_summary=EstimateSummary(total_hours_low=8.0, total_hours_base=14.0, total_hours_high=20.0),
        status=ScopeStatus.PENDING_REVIEW,
        created_at="2026-10-18T10:00:00Z",
        updated_at="2026-10-18T10:00:00Z",
    )

    proposal = agent.generate_proposal(scope)

    assert proposal.scope_id == "scope_test_123"
    assert proposal.client_name == "Coastal Chamber"
    assert proposal.project_name == "Coastal Directory"
    assert proposal.effort_summary.total_hours_base == 14.0
    assert len(proposal.deliverables) == 1
    assert "REQ-001" in proposal.deliverables[0]
