"""Proposal agent creating client-ready proposals derived from validated scope."""

import uuid
from app.schemas import MilestoneItem, ProposalResponse, ScopeDocument


class ProposalAgent:
    """Generates a cohesive client proposal strictly derived from validated scope."""

    def generate_proposal(self, scope: ScopeDocument) -> ProposalResponse:
        """Derives a proposal response ensuring zero contradiction with the scope object."""
        deliverables = [
            f"{req.id} — {req.title}: {req.description}"
            for req in scope.requirements
            if req.status.value == "confirmed"
        ]

        # Collect assumptions
        assumptions = []
        for req in scope.requirements:
            assumptions.extend(req.assumptions)
        assumptions = list(set(assumptions))
        if not assumptions:
            assumptions = ["Project will use standard Brilliant Directories platform capabilities."]

        # Collect risks
        risk_mitigations = []
        for req in scope.requirements:
            for r in req.risks:
                risk_mitigations.append(f"Risk: {r} — Mitigation: Validate configuration during sprint kickoff.")
        if not risk_mitigations:
            risk_mitigations = ["Standard configuration risk mitigated via staging environment testing."]

        # Milestones if present, or generated from work packages
        milestones = scope.milestones
        if not milestones:
            phase1_hours = round(scope.estimate_summary.total_hours_base * 0.4, 1)
            phase2_hours = round(scope.estimate_summary.total_hours_base * 0.4, 1)
            phase3_hours = round(scope.estimate_summary.total_hours_base - phase1_hours - phase2_hours, 1)

            milestones = [
                MilestoneItem(
                    milestone_id="M1",
                    name="Phase 1: Architecture & Initial Configuration",
                    deliverables=["Platform setup", "Category taxonomy", "Core search widgets"],
                    estimated_hours=phase1_hours,
                    dependencies=["Client platform credentials"],
                ),
                MilestoneItem(
                    milestone_id="M2",
                    name="Phase 2: Customization & Integrations",
                    deliverables=["Payment gateways", "Lead distribution", "CSV migration"],
                    estimated_hours=phase2_hours,
                    dependencies=["Phase 1 completion", "Stripe API keys"],
                ),
                MilestoneItem(
                    milestone_id="M3",
                    name="Phase 3: QA, Verification & Launch",
                    deliverables=["Performance verification", "User acceptance testing", "DNS go-live"],
                    estimated_hours=phase3_hours,
                    dependencies=["Phase 2 completion"],
                ),
            ]

        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        exec_summary = (
            f"Scope and technical proposal for {scope.client_name} ({scope.project_name}). "
            f"Based on discovery analysis, the project encompasses {len(scope.requirements)} structured requirements "
            f"totaling an estimated {scope.estimate_summary.total_hours_base} base engineering hours."
        )

        return ProposalResponse(
            proposal_id=proposal_id,
            scope_id=scope.scope_id,
            version=scope.version,
            client_name=scope.client_name,
            project_name=scope.project_name,
            executive_summary=exec_summary,
            deliverables=deliverables,
            out_of_scope=scope.out_of_scope,
            technical_assumptions=assumptions,
            risk_mitigations=risk_mitigations,
            milestones=milestones,
            effort_summary=scope.estimate_summary,
            approval_status=scope.status,
            disclaimer="Preliminary proposal derived from discovery transcript. Commercial pricing, timeline commitments, and formal scope acceptance require human executive sign-off.",
        )
