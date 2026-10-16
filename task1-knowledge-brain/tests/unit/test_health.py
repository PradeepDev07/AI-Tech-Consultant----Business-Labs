"""Unit tests for the health check and root endpoints."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Verify GET /health returns expected status and metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model_provider" in data
    assert "embedding_provider" in data
    assert data["database"] == "sqlite"


def test_root_endpoint():
    """Verify root endpoint returns basic service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Knowledge Brain" in data["service"]
    assert data["health"] == "/health"
