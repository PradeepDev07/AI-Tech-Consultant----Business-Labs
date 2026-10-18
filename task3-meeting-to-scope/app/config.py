"""Application configuration settings for Task 3 Meeting to Scope Agent."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Task 3 environment and operational settings."""

    PORT: int = 8002
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "development"

    # Task 1 Knowledge Brain HTTP API
    TASK1_API_BASE_URL: str = "http://localhost:8000"
    TASK1_API_TIMEOUT_SECONDS: float = 10.0
    TASK1_MAX_RETRIES: int = 3

    # LLM Provider Configuration
    MODEL_PROVIDER: str = "mock"  # "mock" or "ollama"
    MODEL_NAME: str = "mock-scope-model"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Storage
    DATABASE_PATH: str = "storage/meeting_to_scope.db"

    # Input Limits
    MAX_TRANSCRIPT_LENGTH: int = 50000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Returns cached singleton configuration instance."""
    return Settings()
