"""Integration tests for human escalation, expert answer submission, approval, and knowledge re-indexing."""

from fastapi.testclient import TestClient
from app.dependencies import get_vector_store_instance
from app.main import app
from retrieval.embeddings import MockEmbeddingProvider
from retrieval.vector_store import InMemoryVectorStore


def test_escalation_to_reindexed_knowledge_workflow():
    """Verify that an unanswered question can be escalated, answered, approved, and retrieved."""
    embeddings = MockEmbeddingProvider(dim=128)
    store = InMemoryVectorStore(embedding_provider=embeddings)
    app.dependency_overrides[get_vector_store_instance] = lambda: store

    client = TestClient(app)

    # 1. Ask a question about an unindexed topic
    unanswered_q = "How do I setup custom SMTP relay with Amazon SES?"
    resp1 = client.post("/api/v1/questions", json={"question": unanswered_q})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["abstained"] is True  # Model abstains due to no documentation

    # 2. Escalate the question to human expert
    esc_payload = {
        "question": unanswered_q,
        "retrieved_evidence": [c for c in data1["citations"]],
        "user_context": {"user_id": "usr_99"},
    }
    resp2 = client.post("/api/v1/escalations", json=esc_payload)
    assert resp2.status_code == 201
    esc_data = resp2.json()
    escalation_id = esc_data["escalation_id"]
    assert esc_data["status"] == "open"

    # 3. Human expert answers the escalation
    answer_payload = {
        "expert_answer": "To configure Amazon SES SMTP relay, navigate to Settings > Advanced Settings > Email Settings, and enter your SES host email-smtp.us-east-1.amazonaws.com along with port 587 and SMTP credentials.",
        "expert_name": "Senior Support Engineer Alice",
    }
    resp3 = client.post(f"/api/v1/escalations/{escalation_id}/answer", json=answer_payload)
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "answered"

    # 4. Knowledge Admin approves the expert answer (triggers vector re-indexing)
    approve_payload = {
        "approved_by": "Knowledge Manager Bob",
        "reviewer_notes": "Tested in staging environment.",
    }
    resp4 = client.post(f"/api/v1/escalations/{escalation_id}/approve", json=approve_payload)
    assert resp4.status_code == 200
    approved_data = resp4.json()
    assert approved_data["status"] == "approved"
    assert approved_data["reindexed_at"] is not None

    # 5. Ask the exact same question again!
    resp5 = client.post("/api/v1/questions", json={"question": unanswered_q})
    assert resp5.status_code == 200
    data5 = resp5.json()

    # Now the system CAN answer using the approved human expert knowledge!
    assert data5["abstained"] is False
    assert "Amazon SES" in data5["answer"]
    assert len(data5["citations"]) > 0
    assert f"/escalations/{escalation_id}" in data5["citations"][0]["source_url"]

    app.dependency_overrides.clear()
