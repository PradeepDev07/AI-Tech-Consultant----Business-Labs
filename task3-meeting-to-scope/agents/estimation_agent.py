"""Estimation agent producing mathematically consistent effort breakdowns."""

from app.providers.model_provider import BaseModelProvider
from app.schemas import (
    EstimateItem,
    EstimateSummary,
    RequirementCategory,
    RequirementFeasibility,
    RequirementItem,
)


class EstimationAgent:
    """Generates transparent work package effort estimates with explicit uncertainty."""

    def __init__(self, model_provider: BaseModelProvider):
        self.model_provider = model_provider

    async def generate_estimates(
        self,
        requirements: list[RequirementItem],
        feasibility_list: list[RequirementFeasibility] | None = None,
    ) -> tuple[list[EstimateItem], EstimateSummary]:
        """
        Calculates task-level low/base/high estimates and mathematically consistent totals.
        Never invents pricing, hourly rates, or financial commitments.
        """
        feasibility_map = {f.requirement_id: f for f in (feasibility_list or [])}
        estimates: list[EstimateItem] = []

        for req in requirements:
            feasibility = feasibility_map.get(req.id)
            is_unverified = feasibility is None or not feasibility.is_supported

            # Determine baseline effort by category
            if req.category == RequirementCategory.FUNCTIONAL:
                if "lead" in req.title.lower():
                    h_low, h_base, h_high = 8.0, 14.0, 20.0
                else:
                    h_low, h_base, h_high = 10.0, 16.0, 24.0
            elif req.category == RequirementCategory.INTEGRATIONS:
                h_low, h_base, h_high = 6.0, 12.0, 18.0
            elif req.category == RequirementCategory.DATA:
                h_low, h_base, h_high = 6.0, 10.0, 16.0
            elif req.category == RequirementCategory.PERFORMANCE:
                h_low, h_base, h_high = 4.0, 6.0, 10.0
            elif req.category == RequirementCategory.ROLES_AND_PERMISSIONS:
                h_low, h_base, h_high = 3.0, 5.0, 8.0
            else:
                h_low, h_base, h_high = 4.0, 8.0, 14.0

            # Expand uncertainty margin if feasibility is unverified or requirement is ambiguous
            if is_unverified or req.status.value in ["ambiguous", "requires_clarification"]:
                h_high = round(h_high * 1.3, 1)
                confidence = "low"
                requires_val = True
            else:
                confidence = "medium" if req.priority.value == "high" else "high"
                requires_val = False

            estimates.append(
                EstimateItem(
                    requirement_id=req.id,
                    task_description=f"Engineering and configuration for {req.title}",
                    hours_low=h_low,
                    hours_base=h_base,
                    hours_high=h_high,
                    confidence_range=confidence,
                    assumptions=req.assumptions or ["Standard configuration without core engine modifications"],
                    risk_factors=req.risks or [],
                    requires_validation=requires_val,
                )
            )

        # Mathematical total verification
        total_low = round(sum(e.hours_low for e in estimates), 1)
        total_base = round(sum(e.hours_base for e in estimates), 1)
        total_high = round(sum(e.hours_high for e in estimates), 1)

        summary = EstimateSummary(
            total_hours_low=total_low,
            total_hours_base=total_base,
            total_hours_high=total_high,
            currency_rate_status="unpriced_rates_unknown",
            notes="Estimates represent engineering effort ranges (low/base/high). Hourly billing rates, commercial pricing, and fixed-bid terms require explicit human sales review.",
        )

        return estimates, summary
