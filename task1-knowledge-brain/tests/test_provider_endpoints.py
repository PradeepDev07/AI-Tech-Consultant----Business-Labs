"""Tests for Task 1 provider configuration and switching endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.model_provider import get_provider_manager


@pytest.fixture
def client():
    # Reset provider manager to mock before each test
    manager = get_provider_manager()
    manager.set_active_provider("mock")
    return TestClient(app)


def test_get_provider_status(client):
    """GET /api/v1/provider returns provider info without leaking secrets."""
    res = client.get("/api/v1/provider")
    assert res.status_code == 200
    data = res.json()
    assert data["active_provider_type"] == "mock"
    assert "mock" in data["available_providers"]
    assert "ollama" in data["available_providers"]
    assert "claude" in data["available_providers"]
    # Secret key should NOT be present in response
    assert "api_key" not in data
    assert "claude" in data
    assert "configured" in data["claude"]
    assert "api_key" not in data["claude"]


def test_test_provider_mock(client):
    """POST /api/v1/provider/test returns ok for mock."""
    res = client.post("/api/v1/provider/test", json={"provider": "mock"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_test_provider_claude_without_key(client):
    """POST /api/v1/provider/test returns error when Claude key is missing."""
    res = client.post("/api/v1/provider/test", json={"provider": "claude", "api_key": ""})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "error"
    assert "not configured" in data["message"].lower()


def test_select_provider_invalid(client):
    """POST /api/v1/provider/select rejects unknown providers with 400."""
    res = client.post("/api/v1/provider/select", json={"provider": "openai-gpt4"})
    assert res.status_code == 400
    assert "Invalid provider" in res.json()["detail"]


def test_select_provider_mock(client):
    """POST /api/v1/provider/select can switch to mock."""
    res = client.post("/api/v1/provider/select", json={"provider": "mock"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "mock" in data["active_provider"].lower()


def test_select_claude_without_key_fails(client):
    """POST /api/v1/provider/select without key returns 400."""
    manager = get_provider_manager()
    manager._claude_key = ""
    res = client.post("/api/v1/provider/select", json={"provider": "claude", "api_key": ""})
    assert res.status_code == 400
    assert "not configured" in res.json()["detail"].lower()


def test_select_ollama_unreachable_fails(client):
    """POST /api/v1/provider/select with unreachable Ollama returns 503."""
    res = client.post(
        "/api/v1/provider/select",
        json={"provider": "ollama", "base_url": "http://127.0.0.1:59999", "model": "nonexistent"},
    )
    assert res.status_code == 503
    assert "Ollama connection check failed" in res.json()["detail"]


def test_dashboard_endpoint(client):
    """GET /dashboard returns 200 and serves HTML dashboard."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "AI Tech Consultant" in res.text


def test_root_content_negotiation(client):
    """GET / serves HTML when text/html is requested, JSON otherwise."""
    # JSON request (default)
    res_json = client.get("/", headers={"accept": "application/json"})
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers.get("content-type", "")
    assert res_json.json()["service"] == "Knowledge Brain API"

    # HTML request
    res_html = client.get("/", headers={"accept": "text/html,application/xhtml+xml"})
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers.get("content-type", "")
    assert "AI Tech Consultant" in res_html.text
