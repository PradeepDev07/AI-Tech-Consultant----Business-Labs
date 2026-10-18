"""Integration tests for scope change detection and revision approval workflow."""

import os
import pytest
from app.database import Database
from app.schemas import (
    ApprovalAction,
    ApprovalRequest,
    EstimateItem,
    EstimateSummary,
    RequirementCategory,
    RequirementItem,
    RequirementStatus,
    ScopeDocument,
    ScopeStatus,
)
from app.services.approval_service import ApprovalService
from app.services.scope_diff_service import ScopeDiffService


def test_scope_diff_and_revision_lifecycle():
    test_db = "storage/test_diff_lifecycle.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    db = Database(db_path=test_db)
    diff_svc = ScopeDiffService(database=db)
    approval_svc = ApprovalService(database=db)

    # 1. Seed base scope v1
    base_reqs = [
        RequirementItem(
            id="REQ-001",
            category=RequirementCategory.FUNCTIONAL,
            title="Directory Search",
            description="Directory search by city",
            source_quote="quote 1",
            status=RequirementStatus.CONFIRMED,
        ),
        RequirementItem(
            id="REQ-002",
            category=RequirementCategory.DATA,
            title="CSV Migration",
            description="Migrate 2,500 records",
            source_quote="quote 2",
            status=RequirementStatus.CONFIRMED,
        ),
    ]
    base_ests = [
        EstimateItem(requirement_id="REQ-001", task_description="Search", hours_low=8.0, hours_base=14.0, hours_high=20.0),
        EstimateItem(requirement_id="REQ-002", task_description="CSV", hours_low=6.0, hours_base=10.0, hours_high=16.0),
    ]
    base_scope = ScopeDocument(
        scope_id="scope_v1_test",
        version=1,
        transcript_id="tr_v1",
        project_name="Coastal Chamber",
        client_name="Coastal Chamber",
        summary="Base scope v1",
        requirements=base_reqs,
        estimates=base_ests,
        estimate_summary=EstimateSummary(total_hours_low=14.0, total_hours_base=24.0, total_hours_high=36.0),
        status=ScopeStatus.PENDING_REVIEW,
        created_at="2026-10-18T10:00:00Z",
        updated_at="2026-10-18T10:00:00Z",
    )
    db.save_scope(base_scope)

    # 2. Approve base scope v1
    appr_resp = approval_svc.approve_scope(
        base_scope.scope_id,
        ApprovalRequest(action=ApprovalAction.APPROVE, reviewer_name="Lead Architect", reviewer_notes="Approved v1"),
    )
    assert appr_resp.status == ScopeStatus.APPROVED

    # 3. Follow-up meeting adds Lead Matching and removes CSV Migration
    new_reqs = [
        base_reqs[0],  # Directory search unchanged
        RequirementItem(
            id="REQ-003",
            category=RequirementCategory.FUNCTIONAL,
            title="Automated Lead Distribution",
            description="Automated quote matching",
            source_quote="Add lead matching",
            status=RequirementStatus.CONFIRMED,
        ),
    ]
    new_ests = [
        base_ests[0],
        EstimateItem(requirement_id="REQ-003", task_description="Lead matching", hours_low=8.0, hours_base=16.0, hours_high=22.0),
    ]

    diff_report = diff_svc.compare_scopes(
        base_scope=base_scope,
        new_requirements=new_reqs,
        new_estimates=new_ests,
        transcript_text="Add lead matching. Cancel CSV migration task.",
    )

    assert diff_report.has_contradictions is False
    assert diff_report.requires_human_approval is True
    # Lead matching added (+16), CSV removed (-10) -> delta = +6.0 hours
    assert diff_report.total_hours_delta_base == 6.0

    # 4. Approve revision: base scope becomes SUPERSEDED, new approved v2 is created
    rev_resp = approval_svc.approve_revision(
        base_scope_id=base_scope.scope_id,
        diff_id=diff_report.diff_id,
        request=ApprovalRequest(
            action=ApprovalAction.APPROVE,
            reviewer_name="Executive Sponsor",
            reviewer_notes="Approved revision v2",
        ),
    )

    assert rev_resp.new_version_created is True
    assert rev_resp.version == 2

    # Verify base scope is superseded
    base_check = db.get_scope(base_scope.scope_id)
    assert base_check.status == ScopeStatus.SUPERSEDED

    # Verify new scope is approved with version 2
    v2_check = db.get_scope(rev_resp.new_scope_id)
    assert v2_check.version == 2
    assert v2_check.status == ScopeStatus.APPROVED
    assert v2_check.previous_version_id == base_scope.scope_id
    assert v2_check.estimate_summary.total_hours_base == 30.0  # 24 + 6 = 30.0!

    if os.path.exists(test_db):
        os.remove(test_db)
