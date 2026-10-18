"""Unit tests for EstimationAgent."""

import pytest
from agents.estimation_agent import EstimationAgent
from app.providers.model_provider import MockModelProvider
from app.schemas import (
    RequirementCategory,
    RequirementItem,
    RequirementStatus,
)


@pytest.mark.asyncio
async def test_estimation_arithmetic_consistency():
    provider = MockModelProvider()
    agent = EstimationAgent(provider)

    reqs = [
        RequirementItem(
            id="REQ-001",
            category=RequirementCategory.FUNCTIONAL,
            title="Search",
            description="Directory search",
            source_quote="search quote",
            status=RequirementStatus.CONFIRMED,
        ),
        RequirementItem(
            id="REQ-002",
            category=RequirementCategory.INTEGRATIONS,
            title="Payments",
            description="Stripe payments",
            source_quote="stripe quote",
            status=RequirementStatus.CONFIRMED,
        ),
    ]

    estimates, summary = await agent.generate_estimates(reqs)

    assert len(estimates) == 2
    assert summary.total_hours_low == round(sum(e.hours_low for e in estimates), 1)
    assert summary.total_hours_base == round(sum(e.hours_base for e in estimates), 1)
    assert summary.total_hours_high == round(sum(e.hours_high for e in estimates), 1)
    assert summary.currency_rate_status == "unpriced_rates_unknown"
