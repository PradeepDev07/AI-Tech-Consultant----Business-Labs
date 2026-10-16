"""Question answering and citation schemas."""

import uuid
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation to an authoritative source article supporting the answer."""

    article_id: str
    article_title: str
    source_url: str
    heading: str | None = None
    chunk_index: int | None = None
    excerpt: str
    relevance_score: float | None = None


class RetrievalMetadata(BaseModel):
    """Debug and operational metadata about the retrieval phase."""

    total_chunks_retrieved: int
    top_score: float | None = None
    retrieval_method: str = "vector"  # "vector" or "lexical_fallback"
    model_provider_used: str = "ollama"
    latency_ms: float = 0.0


class QuestionRequest(BaseModel):
    """User request asking a natural language question."""

    question: str = Field(
        ..., min_length=2, max_length=1000, description="The user's question"
    )
    top_k: int | None = Field(
        default=None, ge=1, le=20, description="Override retrieval top-k"
    )
    min_evidence_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Override minimum evidence score"
    )


class QuestionResponse(BaseModel):
    """Structured response from the Knowledge Brain grounded answering service."""

    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique trace identifier for this request",
    )
    question: str
    answer: str
    abstained: bool
    abstention_reason: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    retrieval_metadata: RetrievalMetadata
