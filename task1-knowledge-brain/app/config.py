"""Application configuration with Pydantic v2 Settings."""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Configuration settings for Knowledge Brain application."""

    model_config = SettingsConfigDict(
        env_file=(str(ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Environment
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")

    # API Server Configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Storage Paths
    sqlite_db_path: str = Field(
        default="storage/knowledge_brain.db", alias="SQLITE_DB_PATH"
    )
    chroma_persist_dir: str = Field(
        default="storage/chroma_db", alias="CHROMA_PERSIST_DIR"
    )

    # Ingestion & Sitemap
    sitemap_url: str = Field(
        default="https://support.brilliantdirectories.com/support/sitemap.xml",
        alias="SITEMAP_URL",
    )
    crawler_concurrency: int = Field(default=3, alias="CRAWLER_CONCURRENCY")
    crawler_request_delay_seconds: float = Field(
        default=0.5, alias="CRAWLER_REQUEST_DELAY_SECONDS"
    )
    request_timeout_seconds: float = Field(
        default=15.0, alias="REQUEST_TIMEOUT_SECONDS"
    )
    crawler_max_retries: int = Field(default=3, alias="CRAWLER_MAX_RETRIES")
    crawler_backoff_factor: float = Field(default=1.5, alias="CRAWLER_BACKOFF_FACTOR")
    crawler_user_agent: str = Field(
        default="KnowledgeBrainBot/1.0 (+https://support.brilliantdirectories.com)",
        alias="CRAWLER_USER_AGENT",
    )
    scheduled_ingestion_enabled: bool = Field(
        default=False, alias="SCHEDULED_INGESTION_ENABLED"
    )
    scheduled_ingestion_interval_hours: float = Field(
        default=24.0, alias="SCHEDULED_INGESTION_INTERVAL_HOURS"
    )

    # Chunking & Retrieval
    chunk_size: int = Field(default=800, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP")
    retrieval_top_k: int = Field(default=4, alias="RETRIEVAL_TOP_K")
    min_evidence_threshold: float = Field(
        default=0.35, alias="MIN_EVIDENCE_THRESHOLD"
    )

    # LLM Model Provider
    # Options: "mock", "ollama", "anthropic"
    model_provider: str = Field(default="mock", alias="MODEL_PROVIDER")
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )
    chat_model: str = Field(default="mock-model-v1", alias="CHAT_MODEL")

    # Embedding Provider
    # Options: "mock", "ollama", "chroma_default"
    embedding_provider: str = Field(
        default="mock", alias="EMBEDDING_PROVIDER"
    )
    embedding_model: str = Field(
        default="mock-128", alias="EMBEDDING_MODEL"
    )

    # Vision / Multimodal Provider
    # Options: "none", "mock", "ollama", "ocr"
    vision_provider: str = Field(default="none", alias="VISION_PROVIDER")
    vision_model: str = Field(default="llava:latest", alias="VISION_MODEL")
    image_cache_dir: str = Field(
        default="storage/images", alias="IMAGE_CACHE_DIR"
    )

    # Security
    api_auth_token: str | None = Field(default=None, alias="API_AUTH_TOKEN")

    def resolve_sqlite_path(self) -> Path:
        """Return resolved path to SQLite database."""
        path = Path(self.sqlite_db_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_chroma_path(self) -> Path:
        """Return resolved path to Chroma persistence directory."""
        path = Path(self.chroma_persist_dir)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_image_cache_path(self) -> Path:
        """Return resolved path to image cache directory."""
        path = Path(self.image_cache_dir)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        path.mkdir(parents=True, exist_ok=True)
        return path


def get_settings() -> Settings:
    """Factory function for retrieving cached application settings."""
    return Settings()
