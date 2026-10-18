"""Unit tests for FeasibilityAgent."""

import pytest
from agents.feasibility_agent import FeasibilityAgent
from app.client.knowledge_client import KnowledgeLookupResult
from app.schemas import (
    Citation,
    FeasibilityCategory,
    RequirementCategory,
    RequirementItem,
    RequirementStatus,
)


class MockKnowledgeClient:
    def __init__(self, result: KnowledgeLookupResult):
        self.result = result

    async def query_knowledge(self, question: str, top_k: int = 4, min_threshold: float = 0.35):
        return self.result


@pytest.mark.asyncio
async def test_feasibility_supported_by_evidence():
    result = KnowledgeLookupResult(
        success=True,
        abstained=False,
        answer="Stripe is fully supported in Payment Settings.",
        citations=[
            Citation(
                article_id="art_1",
                article_title="Stripe Setup",
                source_url="https://support.brilliantdirectories.com/stripe",
                excerpt="Configure keys in admin.",
            )
        ],
    )
    agent = FeasibilityAgent(MockKnowledgeClient(result))

    req = RequirementItem(
        id="REQ-001",
        category=RequirementCategory.INTEGRATIONS,
        title="Stripe Integration",
        description="Connect Stripe for recurring billing.",
        source_quote="We need Stripe.",
        status=RequirementStatus.CONFIRMED,
    )

    feasibility = await agent.evaluate_feasibility([req])
    assert len(feasibility) == 1
    assert feasibility[0].feasibility_status == FeasibilityCategory.SUPPORTED_BY_EVIDENCE
    assert feasibility[0].is_supported is True
    assert len(feasibility[0].evidence_citations) == 1


@pytest.mark.asyncio
async def test_feasibility_abstention():
    result = KnowledgeLookupResult(
        success=True,
        abstained=True,
        abstention_reason="No relevant documentation.",
        citations=[],
    )
    agent = FeasibilityAgent(MockKnowledgeClient(result))

    req = RequirementItem(
        id="REQ-002",
        category=RequirementCategory.FUNCTIONAL,
        title="Custom Blockchain Module",
        description="Decentralized identity verification.",
        source_quote="We need blockchain.",
        status=RequirementStatus.CONFIRMED,
    )

    feasibility = await agent.evaluate_feasibility([req])
    assert len(feasibility) == 1
    assert feasibility[0].feasibility_status == FeasibilityCategory.INSUFFICIENT_EVIDENCE
    assert feasibility[0].is_supported is False
