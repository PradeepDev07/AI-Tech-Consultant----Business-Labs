"""Dependency injection wiring for FastAPI routes."""

from functools import lru_cache
from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from app.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.services.answer_service import AnswerService
from app.services.article_service import ArticleService
from app.services.database import Database
from app.services.escalation_service import EscalationService
from app.services.model_provider import (
    BaseModelProvider,
    get_model_provider,
    get_provider_manager,
    ProviderManager,
)
from retrieval.embeddings import BaseEmbeddingProvider, get_embedding_provider
from retrieval.retriever import Retriever
from retrieval.vector_store import BaseVectorStore, create_vector_store


@lru_cache()
def get_cached_settings() -> Settings:
    """Provide singleton settings instance."""
    return get_settings()


@lru_cache()
def get_database() -> Database:
    """Provide singleton database instance."""
    settings = get_cached_settings()
    path = settings.resolve_sqlite_path()
    return Database(str(path))


@lru_cache()
def get_embedding_provider_instance() -> BaseEmbeddingProvider:
    """Provide singleton embedding provider instance."""
    settings = get_cached_settings()
    return get_embedding_provider(
        provider_name=settings.embedding_provider,
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )


@lru_cache()
def get_vector_store_instance() -> BaseVectorStore:
    """Provide singleton vector store instance."""
    settings = get_cached_settings()
    embeddings = get_embedding_provider_instance()
    persist_dir = str(settings.resolve_chroma_path())
    store = create_vector_store(
        persist_dir=persist_dir,
        embedding_provider=embeddings,
    )
    if store.count() == 0:
        db = get_database()
        articles, _ = db.list_articles(limit=500, include_deleted=False)
        if articles:
            from retrieval.chunker import ArticleChunker
            chunker = ArticleChunker(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            for art in articles:
                chunks = chunker.chunk_article(art)
                chunk_dicts = [
                    {"chunk_id": c.chunk_id, "text": c.text, "metadata": c.metadata}
                    for c in chunks
                ]
                store.upsert_chunks(chunk_dicts, embedding_provider=embeddings)
    return store


def get_provider_manager_instance() -> ProviderManager:
    """Provide singleton ProviderManager instance."""
    return get_provider_manager()


def get_model_provider_instance() -> BaseModelProvider:
    """Provide currently active LLM model provider instance from ProviderManager."""
    return get_provider_manager().get_active_provider()


# Attach cache_clear for backward compatibility with existing tests
get_model_provider_instance.cache_clear = lambda: None


def get_retriever_instance(
    vector_store: BaseVectorStore = Depends(get_vector_store_instance),
    embeddings: BaseEmbeddingProvider = Depends(get_embedding_provider_instance),
    db: Database = Depends(get_database),
    settings: Settings = Depends(get_cached_settings),
) -> Retriever:
    """Provide Retriever dependency."""
    return Retriever(
        vector_store=vector_store,
        embedding_provider=embeddings,
        db=db,
        default_top_k=settings.retrieval_top_k,
        min_evidence_threshold=settings.min_evidence_threshold,
    )


def get_answer_service(
    retriever: Retriever = Depends(get_retriever_instance),
    model_provider: BaseModelProvider = Depends(get_model_provider_instance),
    settings: Settings = Depends(get_cached_settings),
) -> AnswerService:
    """Provide AnswerService dependency."""
    return AnswerService(
        retriever=retriever,
        model_provider=model_provider,
        min_evidence_threshold=settings.min_evidence_threshold,
    )


def get_article_service(
    db: Database = Depends(get_database),
    vector_store: BaseVectorStore = Depends(get_vector_store_instance),
) -> ArticleService:
    """Provide ArticleService dependency."""
    return ArticleService(db=db, vector_store=vector_store)


def get_escalation_service(
    db: Database = Depends(get_database),
    vector_store: BaseVectorStore = Depends(get_vector_store_instance),
) -> EscalationService:
    """Provide EscalationService dependency."""
    return EscalationService(db=db, vector_store=vector_store)


def verify_api_token(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_cached_settings),
) -> None:
    """Verify bearer token if API_AUTH_TOKEN is configured."""
    if not settings.api_auth_token:
        return

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != settings.api_auth_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or unauthorized API token",
        )
