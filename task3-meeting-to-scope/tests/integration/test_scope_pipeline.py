"""Integration tests for end-to-end scope generation pipeline."""

import os
import pytest
from agents.estimation_agent import EstimationAgent
from agents.feasibility_agent import FeasibilityAgent
from agents.requirements_agent import RequirementsAgent
from app.client.knowledge_client import KnowledgeLookupResult
from app.database import Database
from app.providers.model_provider import MockModelProvider
from app.schemas import Citation, ScopeStatus, TranscriptCreate
from app.services.estimation_service import EstimationService
from app.services.feasibility_service import FeasibilityService
from app.services.requirements_service import RequirementsService
from app.services.transcript_service import TranscriptService


class MockKnowledgeClient:
    async def query_knowledge(self, question: str, top_k: int = 4, min_threshold: float = 0.35):
        return KnowledgeLookupResult(
            success=True,
            abstained=False,
            answer="Feature is natively supported by Brilliant Directories.",
            citations=[
                Citation(
                    article_id="art_1",
                    article_title="Solution Center Guide",
                    source_url="https://support.brilliantdirectories.com/guide",
                    excerpt="Feature guide.",
                )
            ],
            latency_ms=10.0,
        )


@pytest.mark.asyncio
async def test_end_to_end_scope_pipeline():
    test_db = "storage/test_pipeline.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    db = Database(db_path=test_db)
    transcript_svc = TranscriptService(database=db)
    provider = MockModelProvider()
    req_svc = RequirementsService(RequirementsAgent(provider))
    feas_svc = FeasibilityService(FeasibilityAgent(MockKnowledgeClient()))
    est_svc = EstimationService(EstimationAgent(provider))

    # 1. Ingest Transcript
    raw_text = """
    We want a searchable business directory with category filters.
    We also need Stripe payments for recurring subscriptions.
    We have 2,500 members to import from a CSV spreadsheet.
    """
    tr_resp = transcript_svc.ingest_transcript(
        TranscriptCreate(transcript_text=raw_text)
    )
    assert tr_resp.transcript_id.startswith("tr_")

    # 2. Extract Requirements
    reqs, out_of_scope, open_q = await req_svc.extract(tr_resp.content)
    assert len(reqs) >= 3

    # 3. Grounded Feasibility
    feasibility = await feas_svc.evaluate(reqs)
    assert len(feasibility) == len(reqs)
    assert all(f.is_supported for f in feasibility)

    # 4. Estimation
    estimates, summary = await est_svc.generate_estimates(reqs, feasibility)
    assert len(estimates) == len(reqs)
    assert summary.total_hours_base > 0.0

    if os.path.exists(test_db):
        os.remove(test_db)
