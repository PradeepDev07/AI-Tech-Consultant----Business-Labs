"""Scope change detection and delta comparison service."""

import uuid
from datetime import datetime, timezone
from app.database import Database
from app.schemas import (
    DiffChangeType,
    EstimateItem,
    RequirementDiff,
    RequirementItem,
    ScopeDiffReport,
    ScopeDocument,
)


class ScopeDiffService:
    """Detects requirement additions, removals, modifications, and contradictions."""

    def __init__(self, database: Database):
        self.database = database

    def compare_scopes(
        self,
        base_scope: ScopeDocument,
        new_requirements: list[RequirementItem],
        new_estimates: list[EstimateItem] | None = None,
        transcript_text: str = "",
    ) -> ScopeDiffReport:
        """
        Compares new requirements against a saved baseline scope and produces a structured delta report.
        """
        diff_id = f"diff_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        lower_transcript = transcript_text.lower()

        base_req_map = {r.id: r for r in base_scope.requirements}
        base_est_map = {e.requirement_id: e for e in base_scope.estimates}
        new_est_map = {e.requirement_id: e for e in (new_estimates or [])}

        changes: list[RequirementDiff] = []
        has_contradictions = False

        # Check for explicit cancellations / removals in transcript text
        explicit_removals = []
        for r_id, r in base_req_map.items():
            words = r.title.lower().split()
            if any(
                f"cancel {w}" in lower_transcript or f"remove {w}" in lower_transcript or f"no longer need {w}" in lower_transcript
                for w in words if len(w) > 4
            ):
                explicit_removals.append(r_id)

        # 1. Compare requirements present in new list
        matched_base_ids = set()

        for new_r in new_requirements:
            # Check for direct ID match or title match
            matched_base = base_req_map.get(new_r.id)
            if not matched_base:
                # Try finding by title keyword overlap
                for b_id, b_req in base_req_map.items():
                    if b_id not in matched_base_ids and b_req.title.lower() == new_r.title.lower():
                        matched_base = b_req
                        break

            if matched_base:
                matched_base_ids.add(matched_base.id)
                old_est = base_est_map.get(matched_base.id)
                new_est = new_est_map.get(new_r.id)
                old_hours = old_est.hours_base if old_est else 10.0
                new_hours = new_est.hours_base if new_est else old_hours

                # Check for contradiction
                # e.g., Base says "Stripe integration" and new says "Do not use Stripe, only manual wire transfer"
                is_contradiction = (
                    ("stripe" in matched_base.title.lower() and "manual" in new_r.description.lower())
                    or ("monthly" in matched_base.description.lower() and "annual only" in new_r.description.lower())
                    or ("contradict" in new_r.description.lower())
                )

                if is_contradiction:
                    has_contradictions = True
                    changes.append(
                        RequirementDiff(
                            requirement_id=matched_base.id,
                            change_type=DiffChangeType.CONTRADICTION,
                            title=matched_base.title,
                            previous_value=matched_base.description,
                            new_value=new_r.description,
                            reason_and_quote=f"Contradiction identified: '{new_r.source_quote}' conflicts directly with agreed scope.",
                            effort_impact_hours=round(new_hours - old_hours, 1),
                            risk_impact="high",
                            clarification_needed=True,
                        )
                    )
                elif matched_base.description.strip() != new_r.description.strip() or matched_base.priority != new_r.priority:
                    # Modified
                    changes.append(
                        RequirementDiff(
                            requirement_id=matched_base.id,
                            change_type=DiffChangeType.MODIFIED,
                            title=matched_base.title,
                            previous_value=matched_base.description,
                            new_value=new_r.description,
                            reason_and_quote=new_r.source_quote,
                            effort_impact_hours=round(new_hours - old_hours, 1),
                            risk_impact="medium" if abs(new_hours - old_hours) > 4 else "low",
                            clarification_needed=False,
                        )
                    )
                else:
                    # Unchanged
                    changes.append(
                        RequirementDiff(
                            requirement_id=matched_base.id,
                            change_type=DiffChangeType.UNCHANGED,
                            title=matched_base.title,
                            previous_value=matched_base.description,
                            new_value=new_r.description,
                            reason_and_quote="Confirmed identical to baseline scope.",
                            effort_impact_hours=0.0,
                            risk_impact="none",
                            clarification_needed=False,
                        )
                    )
            else:
                # Added requirement!
                new_est = new_est_map.get(new_r.id)
                added_hours = new_est.hours_base if new_est else 12.0
                changes.append(
                    RequirementDiff(
                        requirement_id=new_r.id,
                        change_type=DiffChangeType.ADDED,
                        title=new_r.title,
                        previous_value=None,
                        new_value=new_r.description,
                        reason_and_quote=new_r.source_quote,
                        effort_impact_hours=added_hours,
                        risk_impact="medium",
                        clarification_needed=False,
                    )
                )

        # 2. Check for Removed requirements from base scope
        for b_id, b_req in base_req_map.items():
            if b_id not in matched_base_ids:
                old_est = base_est_map.get(b_id)
                saved_hours = old_est.hours_base if old_est else 10.0
                changes.append(
                    RequirementDiff(
                        requirement_id=b_id,
                        change_type=DiffChangeType.REMOVED,
                        title=b_req.title,
                        previous_value=b_req.description,
                        new_value=None,
                        reason_and_quote=f"Requirement removed or cancelled in follow-up discussion: '{b_req.title}'.",
                        effort_impact_hours=-round(saved_hours, 1),
                        risk_impact="low",
                        clarification_needed=False,
                    )
                )

        total_hours_delta = round(sum(c.effort_impact_hours for c in changes), 1)

        summary_parts = []
        added_count = sum(1 for c in changes if c.change_type == DiffChangeType.ADDED)
        mod_count = sum(1 for c in changes if c.change_type == DiffChangeType.MODIFIED)
        rem_count = sum(1 for c in changes if c.change_type == DiffChangeType.REMOVED)
        con_count = sum(1 for c in changes if c.change_type == DiffChangeType.CONTRADICTION)

        if added_count:
            summary_parts.append(f"{added_count} added")
        if mod_count:
            summary_parts.append(f"{mod_count} modified")
        if rem_count:
            summary_parts.append(f"{rem_count} removed")
        if con_count:
            summary_parts.append(f"{con_count} contradiction(s)")

        diff_summary = f"Scope delta against v{base_scope.version}: " + (
            ", ".join(summary_parts) if summary_parts else "No material changes detected."
        )

        report = ScopeDiffReport(
            diff_id=diff_id,
            base_scope_id=base_scope.scope_id,
            base_version=base_scope.version,
            proposed_version=base_scope.version + 1,
            diff_summary=diff_summary,
            requirement_changes=changes,
            total_hours_delta_base=total_hours_delta,
            has_contradictions=has_contradictions,
            requires_human_approval=bool(added_count or mod_count or rem_count or con_count),
            created_at=now,
        )

        self.database.save_scope_diff(report)
        return report

    def get_diff(self, diff_id: str) -> ScopeDiffReport | None:
        return self.database.get_scope_diff(diff_id)
