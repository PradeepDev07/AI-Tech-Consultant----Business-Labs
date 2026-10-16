"""Pytest configuration and global fixtures."""

import os
from pathlib import Path
import pytest

TEST_DB_PATH = "storage/test_knowledge_brain.db"
os.environ["APP_ENV"] = "testing"
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["MODEL_PROVIDER"] = "mock"
os.environ["SQLITE_DB_PATH"] = TEST_DB_PATH


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Clear test database and dependency caches before each test."""
    from app.dependencies import (
        get_cached_settings,
        get_database,
        get_embedding_provider_instance,
        get_model_provider_instance,
        get_vector_store_instance,
    )

    # Clean up test DB file
    if Path(TEST_DB_PATH).exists():
        try:
            Path(TEST_DB_PATH).unlink()
        except OSError:
            pass

    get_cached_settings.cache_clear()
    get_database.cache_clear()
    get_embedding_provider_instance.cache_clear()
    get_vector_store_instance.cache_clear()
    get_model_provider_instance.cache_clear()

    yield

    if Path(TEST_DB_PATH).exists():
        try:
            Path(TEST_DB_PATH).unlink()
        except OSError:
            pass
