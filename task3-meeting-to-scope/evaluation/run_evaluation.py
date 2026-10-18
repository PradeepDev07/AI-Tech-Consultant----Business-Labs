"""Benchmark evaluation runner for Task 3 Meeting to Scope Agent (24 Scenarios)."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.estimation_agent import EstimationAgent
from agents.feasibility_agent import FeasibilityAgent
from agents.proposal_agent import ProposalAgent
from agents.requirements_agent import RequirementsAgent
from app.client.knowledge_client import KnowledgeBrainClient, KnowledgeLookupResult
from app.database import Database
from app.providers.model_provider import MockModelProvider
from app.schemas import (
    ApprovalAction,
    ApprovalRequest,
    Citation,
    EstimateItem,
    EstimateSummary,
    MilestoneItem,
    RequirementCategory,
    RequirementItem,
    RequirementStatus,
    ScopeDocument,
    ScopeStatus,
)
from app.services.approval_service import ApprovalService
from app.services.scope_diff_service import ScopeDiffService


import argparse
from app.providers.model_provider import BaseModelProvider, MockModelProvider, OllamaModelProvider


async def run_evaluations():
    parser = argparse.ArgumentParser(description="Task 3 Benchmark Evaluation Runner")
    parser.add_argument("--provider", default=os.environ.get("MODEL_PROVIDER", "mock"), choices=["mock", "ollama"], help="Model provider (mock or ollama)")
    parser.add_argument("--model", default=os.environ.get("CHAT_MODEL", "gpt-oss:120b-cloud"), help="Model identifier when using ollama")
    parser.add_argument("--url", default=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"), help="Ollama base URL")
    args, _ = parser.parse_known_args()

    if args.provider == "ollama":
        model_provider = OllamaModelProvider(base_url=args.url, model_name=args.model)
    else:
        model_provider = MockModelProvider()

    print("==========================================================================")
    print(f"🧪 TASK 3: MEETING TO SCOPE AGENT BENCHMARK EVALUATIONS [{model_provider.provider_name}]")
    print("==========================================================================\n")

    cases_path = Path(__file__).resolve().parent / "cases.json"
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    test_db_path = "storage/test_eval.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    database = Database(db_path=test_db_path)
    req_agent = RequirementsAgent(model_provider=model_provider)
    est_agent = EstimationAgent(model_provider=model_provider)
    prop_agent = ProposalAgent()
    diff_service = ScopeDiffService(database=database)
    approval_service = ApprovalService(database=database)

    results = []

    for case in cases:
        case_id = case["id"]
        case_name = case["name"]
        case_type = case.get("type", "standard")
        expected = case["expected"]
        failures = []

        try:
            if case_type == "standard":
                # Mock Task 1 response if provided in case
                mock_t1 = case.get("mock_task1")

                class MockKnowledgeClient:
                    async def query_knowledge(self, question: str, top_k: int = 4, min_threshold: float = 0.35):
                        if mock_t1:
                            citations = [
                                Citation(**c) for c in mock_t1.get("citations", [])
                            ]
                            return KnowledgeLookupResult(
                                success=mock_t1.get("success", True),
                                abstained=mock_t1.get("abstained", False),
                                abstention_reason=mock_t1.get("abstention_reason"),
                                answer=mock_t1.get("answer", ""),
                                citations=citations,
                                error=mock_t1.get("error"),
                                latency_ms=10.0,
                            )
                        # Default mock Task 1 response
                        return KnowledgeLookupResult(
                            success=True,
                            abstained=False,
                            answer="Brilliant Directories provides verified settings for this capability.",
                            citations=[
                                Citation(
                                    article_id="art_default",
                                    article_title="Verified Solution Center Guide",
                                    source_url="https://support.brilliantdirectories.com/guide",
                                    excerpt="Feature is configured in admin panel.",
                                )
                            ],
                            latency_ms=10.0,
                        )

                feas_agent = FeasibilityAgent(knowledge_client=MockKnowledgeClient())

                # 1. Extract requirements
                transcript = case["input_transcript"]
                requirements, out_of_scope, open_questions = await req_agent.extract_requirements(transcript)

                # 2. Feasibility
                feasibility = await feas_agent.evaluate_feasibility(requirements)

                # 3. Estimates
                estimates, estimate_summary = await est_agent.generate_estimates(requirements, feasibility)

                # Assertions
                if "min_requirements" in expected and len(requirements) < expected["min_requirements"]:
                    failures.append(f"Expected at least {expected['min_requirements']} requirements, got {len(requirements)}")

                if "categories_present" in expected:
                    cats = [r.category.value for r in requirements]
                    for exp_cat in expected["categories_present"]:
                        if exp_cat not in cats:
                            failures.append(f"Category '{exp_cat}' missing from extracted categories {cats}")

                if expected.get("has_quotes") and not all(r.source_quote for r in requirements):
                    failures.append("Not all requirements have source quotes for provenance")

                if expected.get("requires_acceptance_criteria") and not all(r.acceptance_criteria for r in requirements):
                    failures.append("Missing acceptance criteria on one or more requirements")

                if expected.get("timeline_flagged") and not any("Timeline" in q for q in open_questions):
                    failures.append("Ambiguous timeline was not flagged in open questions")

                if expected.get("budget_flagged") and not any("budget" in q.lower() for q in open_questions):
                    failures.append("Missing budget was not flagged in open questions")

                if "feasibility_status" in expected:
                    statuses = [f.feasibility_status.value for f in feasibility]
                    if expected["feasibility_status"] not in statuses:
                        failures.append(f"Expected feasibility status '{expected['feasibility_status']}', got {statuses}")

                if "is_supported" in expected:
                    if not any(f.is_supported == expected["is_supported"] for f in feasibility):
                        failures.append(f"is_supported flag mismatch, expected {expected['is_supported']}")

                if expected.get("currency_rate_status") and estimate_summary.currency_rate_status != expected["currency_rate_status"]:
                    failures.append(f"Currency status mismatch, expected {expected['currency_rate_status']}")

                if expected.get("exact_sum_match"):
                    calc_low = round(sum(e.hours_low for e in estimates), 1)
                    calc_base = round(sum(e.hours_base for e in estimates), 1)
                    calc_high = round(sum(e.hours_high for e in estimates), 1)
                    if (
                        estimate_summary.total_hours_low != calc_low
                        or estimate_summary.total_hours_base != calc_base
                        or estimate_summary.total_hours_high != calc_high
                    ):
                        failures.append(f"Estimate sum mismatch: computed ({calc_low}, {calc_base}, {calc_high}) vs summary ({estimate_summary.total_hours_low}, {estimate_summary.total_hours_base}, {estimate_summary.total_hours_high})")

                if expected.get("quarantined"):
                    inj_req = next((r for r in requirements if r.category == RequirementCategory.SECURITY_AND_PRIVACY), None)
                    if not inj_req:
                        failures.append("Adversarial prompt injection was not quarantined into security category")

            elif case_type == "scope_diff":
                # Create a baseline scope v1
                base_reqs = [
                    RequirementItem(
                        id="REQ-001",
                        category=RequirementCategory.FUNCTIONAL,
                        title="Member Directory and Search",
                        description="Implement searchable business directory with category filters.",
                        source_quote="Directory search requirement.",
                        status=RequirementStatus.CONFIRMED,
                        priority="high",
                    ),
                    RequirementItem(
                        id="REQ-002",
                        category=RequirementCategory.DATA,
                        title="Member Data CSV Migration",
                        description="Import legacy member profiles from CSV export.",
                        source_quote="CSV migration requirement.",
                        status=RequirementStatus.CONFIRMED,
                        priority="high",
                    ),
                ]
                base_ests = [
                    EstimateItem(requirement_id="REQ-001", task_description="Search", hours_low=8.0, hours_base=14.0, hours_high=20.0),
                    EstimateItem(requirement_id="REQ-002", task_description="CSV", hours_low=6.0, hours_base=10.0, hours_high=16.0),
                ]
                base_scope = ScopeDocument(
                    scope_id=f"base_{case_id}",
                    version=1,
                    transcript_id="tr_base",
                    project_name="Base Project",
                    client_name="Base Client",
                    summary="Base scope v1",
                    requirements=base_reqs,
                    estimates=base_ests,
                    estimate_summary=EstimateSummary(total_hours_low=14.0, total_hours_base=24.0, total_hours_high=36.0),
                    status=ScopeStatus.APPROVED,
                    created_at="2026-10-18T10:00:00Z",
                    updated_at="2026-10-18T10:00:00Z",
                )
                database.save_scope(base_scope)

                scenario = case.get("diff_scenario")
                if scenario == "added_feature":
                    new_reqs = list(base_reqs) + [
                        RequirementItem(
                            id="REQ-003",
                            category=RequirementCategory.FUNCTIONAL,
                            title="Automated Lead Distribution",
                            description="Automatically match and dispatch quote inquiries to members.",
                            source_quote="We also want automated lead matching.",
                            status=RequirementStatus.CONFIRMED,
                            priority="high",
                        )
                    ]
                    new_ests = list(base_ests) + [
                        EstimateItem(requirement_id="REQ-003", task_description="Lead matching", hours_low=8.0, hours_base=16.0, hours_high=22.0)
                    ]
                    diff = diff_service.compare_scopes(base_scope, new_reqs, new_ests, "We also want automated lead matching.")
                    if expected.get("has_added_change") and not any(c.change_type.value == "added" for c in diff.requirement_changes):
                        failures.append("Added requirement was not detected in diff report")
                    if expected.get("positive_hours_delta") and diff.total_hours_delta_base <= 0:
                        failures.append("Total hours delta should be positive for added feature")

                elif scenario == "modified_feature":
                    new_reqs = [
                        RequirementItem(
                            id="REQ-001",
                            category=RequirementCategory.FUNCTIONAL,
                            title="Member Directory and Search",
                            description="Modified: advanced radius search with instant auto-complete.",
                            source_quote="We want advanced radius search.",
                            status=RequirementStatus.CONFIRMED,
                            priority="high",
                        ),
                        base_reqs[1],
                    ]
                    new_ests = [
                        EstimateItem(requirement_id="REQ-001", task_description="Search modified", hours_low=12.0, hours_base=20.0, hours_high=28.0),
                        base_ests[1],
                    ]
                    diff = diff_service.compare_scopes(base_scope, new_reqs, new_ests, "We want advanced radius search.")
                    if expected.get("has_modified_change") and not any(c.change_type.value == "modified" for c in diff.requirement_changes):
                        failures.append("Modified requirement was not detected in diff report")

                elif scenario == "removed_feature":
                    new_reqs = [base_reqs[0]]  # Only search kept
                    new_ests = [base_ests[0]]
                    diff = diff_service.compare_scopes(base_scope, new_reqs, new_ests, "Cancel the CSV migration task.")
                    if expected.get("has_removed_change") and not any(c.change_type.value == "removed" for c in diff.requirement_changes):
                        failures.append("Removed requirement was not detected in diff report")
                    if expected.get("negative_hours_delta") and diff.total_hours_delta_base >= 0:
                        failures.append("Total hours delta should be negative for removed feature")

                elif scenario == "contradiction_change":
                    new_reqs = [
                        RequirementItem(
                            id="REQ-001",
                            category=RequirementCategory.FUNCTIONAL,
                            title="Member Directory and Search",
                            description="We contradict our earlier plan and do not allow directory search by city.",
                            source_quote="We contradict search.",
                            status=RequirementStatus.AMBIGUOUS,
                            priority="high",
                        )
                    ]
                    diff = diff_service.compare_scopes(base_scope, new_reqs, base_ests, "Contradict search.")
                    if expected.get("has_contradictions") and not diff.has_contradictions:
                        failures.append("Contradiction was not flagged in diff report")

            elif case_type == "approval":
                # Seed scope
                test_scope = ScopeDocument(
                    scope_id=f"scope_app_{case_id}",
                    version=1,
                    transcript_id="tr_app",
                    project_name="Approval Project",
                    client_name="Approval Client",
                    summary="Test approval scope",
                    requirements=[],
                    estimates=[],
                    estimate_summary=EstimateSummary(total_hours_low=10.0, total_hours_base=15.0, total_hours_high=20.0),
                    status=ScopeStatus.PENDING_REVIEW,
                    created_at="2026-10-18T12:00:00Z",
                    updated_at="2026-10-18T12:00:00Z",
                )
                database.save_scope(test_scope)

                action = case.get("action")
                req_payload = ApprovalRequest(
                    action=ApprovalAction.APPROVE if "approve" in action else ApprovalAction.REJECT,
                    reviewer_name="Senior Reviewer",
                    reviewer_notes="Verified decision",
                )

                if action == "reject":
                    resp = approval_service.reject_scope(test_scope.scope_id, req_payload)
                    if resp.status.value != expected["resulting_status"]:
                        failures.append(f"Expected status {expected['resulting_status']}, got {resp.status.value}")

                elif action == "approve_revision":
                    # First approve base scope
                    approval_service.approve_scope(test_scope.scope_id, req_payload)

                    # Create a diff
                    diff_report = diff_service.compare_scopes(
                        test_scope,
                        [
                            RequirementItem(
                                id="REQ-NEW",
                                category=RequirementCategory.FUNCTIONAL,
                                title="New Approved Feature",
                                description="Feature added in revision.",
                                source_quote="Add new feature.",
                                status=RequirementStatus.CONFIRMED,
                                priority="high",
                            )
                        ],
                        transcript_text="Add new feature",
                    )

                    rev_resp = approval_service.approve_revision(test_scope.scope_id, diff_report.diff_id, req_payload)
                    base_after = database.get_scope(test_scope.scope_id)
                    new_after = database.get_scope(rev_resp.new_scope_id)

                    if rev_resp.version != expected["new_version"]:
                        failures.append(f"Expected new version {expected['new_version']}, got {rev_resp.version}")
                    if base_after.status.value != expected["base_status"]:
                        failures.append(f"Base scope status should be '{expected['base_status']}', got '{base_after.status.value}'")
                    if new_after.status.value != expected["new_status"]:
                        failures.append(f"New scope status should be '{expected['new_status']}', got '{new_after.status.value}'")

        except Exception as exc:
            failures.append(f"Unhandled exception during evaluation: {str(exc)}")

        passed = len(failures) == 0
        results.append({
            "id": case_id,
            "name": case_name,
            "passed": passed,
            "failures": failures,
        })

    # Print results table
    print("| ID | Scenario Name | Result |")
    print("|---|---|---|")

    passed_count = 0
    for r in results:
        status_icon = "✅ PASS" if r["passed"] else "❌ FAIL"
        if r["passed"]:
            passed_count += 1
        print(f"| {r['id']} | {r['name']} | {status_icon} |")
        if not r["passed"]:
            for f in r["failures"]:
                print(f"   ↳ ❌ {f}")

    print("\n==========================================================================")
    print(f"EVALUATION SUMMARY: {passed_count}/{len(results)} PASSED ({round(passed_count / len(results) * 100)}%)")
    print(f"MODEL PROVIDER:     {model_provider.provider_name}")
    print("==========================================================================")

    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    if passed_count < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_evaluations())
