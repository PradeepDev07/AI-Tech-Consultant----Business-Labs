"""Integration tests for Task 3 FastAPI endpoints."""

import os
import pytest
from fastapi.testclient import TestClient
from app.client.knowledge_client import KnowledgeLookupResult
from app.database import Database
from app.dependencies import get_database, get_knowledge_client
from app.main import app
from app.schemas import Citation


class MockKnowledgeClient:
    async def query_knowledge(self, question: str, top_k: int = 4, min_threshold: float = 0.35):
        return KnowledgeLookupResult(
            success=True,
            abstained=False,
            answer="Feature is documented in Brilliant Directories.",
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


test_db_path = "storage/test_api_endpoints.db"


@pytest.fixture(autouse=True)
def setup_test_db():
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    test_db = Database(db_path=test_db_path)
    app.dependency_overrides[get_database] = lambda: test_db
    app.dependency_overrides[get_knowledge_client] = lambda: MockKnowledgeClient()
    yield
    app.dependency_overrides.clear()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_api_endpoints_workflow():
    client = TestClient(app)

    # 1. GET /health
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"
    assert health_resp.json()["service"] == "task3-meeting-to-scope"

    # 2. POST /api/v1/transcripts
    tr_payload = {
        "transcript_text": "We need a member directory with search by category and Stripe payments.",
        "metadata": {
            "project_name": "API Test Project",
            "client_name": "API Test Client",
        },
    }
    tr_resp = client.post("/api/v1/transcripts", json=tr_payload)
    assert tr_resp.status_code == 201
    tr_data = tr_resp.json()
    transcript_id = tr_data["transcript_id"]

    # 3. GET /api/v1/transcripts/{id}
    get_tr = client.get(f"/api/v1/transcripts/{transcript_id}")
    assert get_tr.status_code == 200
    assert get_tr.json()["transcript_id"] == transcript_id

    # 4. POST /api/v1/scope/generate
    scope_gen_resp = client.post(
        "/api/v1/scope/generate",
        json={"transcript_id": transcript_id, "project_name": "API Project", "client_name": "Client X"},
    )
    assert scope_gen_resp.status_code == 201
    scope_data = scope_gen_resp.json()
    scope_id = scope_data["scope_id"]
    assert scope_data["version"] == 1
    assert scope_data["status"] == "pending_review"

    # 5. GET /api/v1/scope/{id}
    get_scope = client.get(f"/api/v1/scope/{scope_id}")
    assert get_scope.status_code == 200
    assert get_scope.json()["scope_id"] == scope_id

    # 6. POST /api/v1/scope/{id}/approve
    approve_resp = client.post(
        f"/api/v1/scope/{scope_id}/approve",
        json={"action": "approve", "reviewer_name": "Principal Engineer", "reviewer_notes": "LGTM"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # 7. GET /api/v1/proposals/{scope_id}
    prop_resp = client.get(f"/api/v1/proposals/{scope_id}")
    assert prop_resp.status_code == 200
    prop_data = prop_resp.json()
    assert prop_data["scope_id"] == scope_id
    assert prop_data["client_name"] == "Client X"
    assert len(prop_data["deliverables"]) > 0

    # 8. POST /api/v1/scope/{scope_id}/diff
    diff_resp = client.post(
        f"/api/v1/scope/{scope_id}/diff",
        json={"change_request_text": "We also want automated lead matching for member quote requests."},
    )
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()
    diff_id = diff_data["diff_id"]
    assert diff_data["requires_human_approval"] is True

    # 9. POST /api/v1/scope/{scope_id}/revisions/{diff_id}/approve
    rev_resp = client.post(
        f"/api/v1/scope/{scope_id}/revisions/{diff_id}/approve",
        json={"action": "approve", "reviewer_name": "VP Product", "reviewer_notes": "Approved lead matching"},
    )
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["new_version_created"] is True
    assert rev_data["version"] == 2
