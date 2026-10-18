"""Unit tests for KnowledgeBrainClient."""

import pytest
import httpx
from app.client.knowledge_client import KnowledgeBrainClient


@pytest.mark.asyncio
async def test_knowledge_client_success(monkeypatch):
    mock_payload = {
        "request_id": "req_123",
        "question": "How to setup Stripe?",
        "answer": "Configure Stripe in Settings > Payment Gateways.",
        "abstained": False,
        "abstention_reason": None,
        "citations": [
            {
                "article_id": "art_1",
                "article_title": "Stripe Gateway",
                "source_url": "https://support.brilliantdirectories.com/stripe",
                "excerpt": "Stripe settings.",
            }
        ],
    }

    class MockResponse:
        status_code = 200
        def json(self):
            return mock_payload

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, url, json, headers):
            return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    client = KnowledgeBrainClient(base_url="http://localhost:8000")
    result = await client.query_knowledge("How to setup Stripe?")

    assert result.success is True
    assert result.abstained is False
    assert result.answer == "Configure Stripe in Settings > Payment Gateways."
    assert len(result.citations) == 1
    assert result.citations[0].article_id == "art_1"


@pytest.mark.asyncio
async def test_knowledge_client_client_error(monkeypatch):
    class MockErrorResponse:
        status_code = 400
        text = "Bad Request"

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, url, json, headers):
            return MockErrorResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    client = KnowledgeBrainClient(base_url="http://localhost:8000", max_retries=3)
    result = await client.query_knowledge("Bad request")

    assert result.success is False
    assert result.abstained is True
    assert "Client error HTTP 400" in result.error
