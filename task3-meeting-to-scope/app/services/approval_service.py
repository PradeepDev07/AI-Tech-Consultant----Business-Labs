"""Human review, versioning, and approval management service."""

import uuid
from datetime import datetime, timezone
from app.database import Database
from app.schemas import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalResponse,
    DiffChangeType,
    EstimateItem,
    EstimateSummary,
    RequirementItem,
    RequirementStatus,
    ScopeDocument,
    ScopeStatus,
)


class ApprovalService:
    """Enforces human-in-the-loop review, immutability of approved scopes, and version progression."""

    def __init__(self, database: Database):
        self.database = database

    def approve_scope(self, scope_id: str, request: ApprovalRequest) -> ApprovalResponse:
        """Approves a draft or pending scope."""
        scope = self.database.get_scope(scope_id)
        if not scope:
            raise ValueError(f"Scope not found: {scope_id}")

        if scope.status == ScopeStatus.APPROVED:
            raise ValueError(f"Scope {scope_id} is already approved.")

        now = datetime.now(timezone.utc).isoformat()
        scope.status = ScopeStatus.APPROVED
        scope.approved_by = request.reviewer_name
        scope.approved_at = now
        scope.updated_at = now

        self.database.save_scope(scope)
        self.database.log_approval_action(
            scope_id=scope.scope_id,
            version=scope.version,
            action=ApprovalAction.APPROVE,
            reviewer_name=request.reviewer_name,
            notes=request.reviewer_notes,
            timestamp=now,
        )

        return ApprovalResponse(
            scope_id=scope.scope_id,
            version=scope.version,
            status=scope.status,
            action=ApprovalAction.APPROVE,
            reviewed_by=request.reviewer_name,
            timestamp=now,
            message=f"Scope v{scope.version} has been approved by {request.reviewer_name}.",
            new_version_created=False,
        )

    def reject_scope(self, scope_id: str, request: ApprovalRequest) -> ApprovalResponse:
        """Rejects a draft or proposed revision."""
        scope = self.database.get_scope(scope_id)
        if not scope:
            raise ValueError(f"Scope not found: {scope_id}")

        now = datetime.now(timezone.utc).isoformat()
        scope.status = ScopeStatus.REJECTED
        scope.updated_at = now

        self.database.save_scope(scope)
        self.database.log_approval_action(
            scope_id=scope.scope_id,
            version=scope.version,
            action=ApprovalAction.REJECT,
            reviewer_name=request.reviewer_name,
            notes=request.reviewer_notes,
            timestamp=now,
        )

        return ApprovalResponse(
            scope_id=scope.scope_id,
            version=scope.version,
            status=scope.status,
            action=ApprovalAction.REJECT,
            reviewed_by=request.reviewer_name,
            timestamp=now,
            message=f"Scope v{scope.version} was rejected by {request.reviewer_name}.",
            new_version_created=False,
        )

    def approve_revision(
        self,
        base_scope_id: str,
        diff_id: str,
        request: ApprovalRequest,
    ) -> ApprovalResponse:
        """
        Approves a scope difference report, marking the base scope superseded and
        creating an immutable new approved version (vN+1).
        """
        base_scope = self.database.get_scope(base_scope_id)
        if not base_scope:
            raise ValueError(f"Base scope not found: {base_scope_id}")

        diff = self.database.get_scope_diff(diff_id)
        if not diff:
            raise ValueError(f"Scope diff report not found: {diff_id}")

        now = datetime.now(timezone.utc).isoformat()

        # 1. Supersede base scope
        base_scope.status = ScopeStatus.SUPERSEDED
        base_scope.updated_at = now
        self.database.save_scope(base_scope)

        # 2. Build revised requirements and estimates
        new_req_list: list[RequirementItem] = []
        base_req_map = {r.id: r for r in base_scope.requirements}

        # Apply diffs
        for change in diff.requirement_changes:
            if change.change_type == DiffChangeType.ADDED:
                new_req_list.append(
                    RequirementItem(
                        id=change.requirement_id,
                        category=base_scope.requirements[0].category if base_scope.requirements else "functional",
                        title=change.title,
                        description=change.new_value or change.title,
                        source_quote=change.reason_and_quote,
                        status=RequirementStatus.CONFIRMED,
                        priority="high",
                        acceptance_criteria=["Validated in revised scope"],
                        assumptions=[],
                        risks=[],
                        dependencies=[],
                        confidence_score=1.0,
                    )
                )
            elif change.change_type in [DiffChangeType.UNCHANGED, DiffChangeType.MODIFIED]:
                existing = base_req_map.get(change.requirement_id)
                if existing:
                    if change.change_type == DiffChangeType.MODIFIED and change.new_value:
                        existing.description = change.new_value
                    new_req_list.append(existing)

        # 3. Build updated estimate summary
        new_total_base = round(base_scope.estimate_summary.total_hours_base + diff.total_hours_delta_base, 1)
        new_total_low = round(base_scope.estimate_summary.total_hours_low + (diff.total_hours_delta_base * 0.7), 1)
        new_total_high = round(base_scope.estimate_summary.total_hours_high + (diff.total_hours_delta_base * 1.3), 1)

        new_estimate_summary = EstimateSummary(
            total_hours_low=max(new_total_low, 0.0),
            total_hours_base=max(new_total_base, 0.0),
            total_hours_high=max(new_total_high, 0.0),
            currency_rate_status="unpriced_rates_unknown",
            notes=f"Revised scope v{base_scope.version + 1} incorporating approved scope changes.",
        )

        new_scope_id = f"scope_{uuid.uuid4().hex[:10]}"
        revised_scope = ScopeDocument(
            scope_id=new_scope_id,
            version=base_scope.version + 1,
            transcript_id=base_scope.transcript_id,
            project_name=base_scope.project_name,
            client_name=base_scope.client_name,
            summary=f"{base_scope.summary} (Revised v{base_scope.version + 1}: {diff.diff_summary})",
            business_objectives=base_scope.business_objectives,
            requirements=new_req_list or base_scope.requirements,
            feasibility_analysis=base_scope.feasibility_analysis,
            estimates=base_scope.estimates,
            estimate_summary=new_estimate_summary,
            out_of_scope=base_scope.out_of_scope,
            open_questions=base_scope.open_questions,
            milestones=base_scope.milestones,
            status=ScopeStatus.APPROVED,
            approved_by=request.reviewer_name,
            approved_at=now,
            previous_version_id=base_scope.scope_id,
            created_at=now,
            updated_at=now,
        )

        self.database.save_scope(revised_scope)
        self.database.log_approval_action(
            scope_id=revised_scope.scope_id,
            version=revised_scope.version,
            action=ApprovalAction.APPROVE,
            reviewer_name=request.reviewer_name,
            notes=f"Approved revision from diff {diff_id}. {request.reviewer_notes or ''}",
            timestamp=now,
        )

        return ApprovalResponse(
            scope_id=revised_scope.scope_id,
            version=revised_scope.version,
            status=revised_scope.status,
            action=ApprovalAction.APPROVE,
            reviewed_by=request.reviewer_name,
            timestamp=now,
            message=f"Created immutable approved scope v{revised_scope.version} referencing previous version {base_scope.scope_id}.",
            new_version_created=True,
            new_scope_id=revised_scope.scope_id,
        )
