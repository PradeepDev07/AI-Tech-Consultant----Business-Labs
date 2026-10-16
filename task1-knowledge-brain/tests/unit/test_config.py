"""Unit tests for configuration loading and validation."""

import os
from app.config import Settings


def test_default_settings():
    """Verify default settings initialization."""
    settings = Settings()
    assert settings.app_env in ["development", "testing", "production"]
    assert settings.api_port == 8000
    assert "brilliantdirectories.com" in settings.sitemap_url
    assert settings.chunk_size > 0
    assert settings.retrieval_top_k >= 1


def test_settings_custom_env(monkeypatch):
    """Verify settings override via environment variables."""
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("API_PORT", "9090")
    monkeypatch.setenv("RETRIEVAL_TOP_K", "10")

    settings = Settings()
    assert settings.app_env == "testing"
    assert settings.api_port == 9090
    assert settings.retrieval_top_k == 10
