"""Retriever orchestrating semantic vector search, deduplication, deleted source filtering, and lexical fallback."""

from dataclasses import dataclass
import re
from typing import Any
from app.core.exceptions import RetrievalError
from app.core.logging import logger
from app.schemas.questions import Citation
from app.services.database import Database
from retrieval.embeddings import BaseEmbeddingProvider
from retrieval.vector_store import BaseVectorStore


@dataclass
class RetrievedEvidence:
    """A verified evidence chunk ready for question answering context."""

    chunk_id: str
    article_id: str
    article_title: str
    source_url: str
    heading: str | None
    chunk_index: int | None
    text: str
    score: float
    excerpt: str

    def to_citation(self) -> Citation:
        """Convert evidence chunk into an API Citation."""
        return Citation(
            article_id=self.article_id,
            article_title=self.article_title,
            source_url=self.source_url,
            heading=self.heading,
            chunk_index=self.chunk_index,
            excerpt=self.excerpt,
            relevance_score=round(self.score, 4),
        )


@dataclass
class RetrievalResult:
    """Output bundle from the retrieval phase."""

    evidence: list[RetrievedEvidence]
    citations: list[Citation]
    top_score: float | None
    sufficient_evidence: bool
    retrieval_method: str
    model_provider_used: str
    latency_ms: float


class Retriever:
    """Semantic vector retriever with source validation, deduplication, and thresholding."""

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedding_provider: BaseEmbeddingProvider,
        db: Database | None = None,
        default_top_k: int = 4,
        min_evidence_threshold: float = 0.35,
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.db = db
        self.default_top_k = default_top_k
        self.min_evidence_threshold = min_evidence_threshold

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        min_threshold: float | None = None,
    ) -> RetrievalResult:
        """Search vector store, filter deleted articles, deduplicate, and verify threshold."""
        import time

        start_time = time.perf_counter()
        k = top_k or self.default_top_k
        threshold = min_threshold if min_threshold is not None else self.min_evidence_threshold

        try:
            query_embedding = self.embedding_provider.embed_text(query)
            # Query vector store for candidates (fetch 2x top_k to account for filtering and deduplication)
            candidates = self.vector_store.query(
                query_embedding=query_embedding, top_k=max(k * 2, 8)
            )
        except Exception as e:
            raise RetrievalError(f"Vector search failed: {e}") from e

        # 1. Filter out deleted or removed sources using DB if available
        valid_candidates = []
        for item in candidates:
            meta = item.get("metadata", {})
            article_id = meta.get("article_id")
            source_type = meta.get("source_type")

            # Check if source article has been soft deleted
            if self.db and article_id and source_type != "approved_expert_answer":
                art = self.db.get_article(article_id)
                if not art or art.get("is_deleted") or art.get("status") == "removed":
                    logger.debug(f"Filtering out deleted source article {article_id}")
                    continue

            valid_candidates.append(item)

        # 2. Deduplicate repeated evidence across chunks
        deduped_evidence: list[RetrievedEvidence] = []
        seen_texts: set[str] = set()

        for item in valid_candidates:
            text = item["text"]
            meta = item.get("metadata", {})
            score = float(item.get("score", 0.0))

            # Simple fingerprint to eliminate identical or nearly identical duplicate chunks
            fingerprint = " ".join(text.split()[:25]).lower()
            if fingerprint in seen_texts:
                continue
            seen_texts.add(fingerprint)

            # Build excerpt (up to 200 chars)
            clean_excerpt = " ".join(text.split()).strip()
            if len(clean_excerpt) > 250:
                clean_excerpt = clean_excerpt[:247] + "..."

            chunk_idx = meta.get("chunk_index")
            if chunk_idx is not None:
                try:
                    chunk_idx = int(chunk_idx)
                except ValueError:
                    chunk_idx = None

            ev = RetrievedEvidence(
                chunk_id=item.get("chunk_id", ""),
                article_id=meta.get("article_id", "unknown"),
                article_title=meta.get("title", "Solution Center Article"),
                source_url=meta.get("source_url", ""),
                heading=meta.get("heading"),
                chunk_index=chunk_idx,
                text=text,
                score=score,
                excerpt=clean_excerpt,
            )
            deduped_evidence.append(ev)
            if len(deduped_evidence) >= k:
                break

        top_score = deduped_evidence[0].score if deduped_evidence else None
        sufficient = bool(top_score is not None and top_score >= threshold)

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return RetrievalResult(
            evidence=deduped_evidence,
            citations=[ev.to_citation() for ev in deduped_evidence],
            top_score=top_score,
            sufficient_evidence=sufficient,
            retrieval_method="vector",
            model_provider_used=self.embedding_provider.provider_name,
            latency_ms=round(latency_ms, 2),
        )


class LexicalRetriever:
    """Explicit keyword/lexical fallback retriever when vector indexing is unavailable."""

    def __init__(self, db: Database, default_top_k: int = 4):
        self.db = db
        self.default_top_k = default_top_k

    def retrieve(
        self, query: str, top_k: int | None = None, min_threshold: float | None = None
    ) -> RetrievalResult:
        """Search articles using term overlap score."""
        import time

        start_time = time.perf_counter()
        k = top_k or self.default_top_k
        query_terms = set(re.findall(r"\w+", query.lower()))
        if not query_terms:
            return RetrievalResult(
                evidence=[],
                citations=[],
                top_score=None,
                sufficient_evidence=False,
                retrieval_method="lexical_fallback",
                model_provider_used="none (lexical)",
                latency_ms=0.0,
            )

        articles, _ = self.db.list_articles(limit=1000, include_deleted=False)
        scored: list[tuple[float, dict[str, Any]]] = []

        for art in articles:
            text = (art["title"] + " " + art["content"]).lower()
            matches = sum(1 for term in query_terms if term in text)
            if matches > 0:
                score = matches / len(query_terms)
                scored.append((score, art))

        scored.sort(key=lambda x: x[0], reverse=True)

        evidence: list[RetrievedEvidence] = []
        for score, art in scored[:k]:
            clean_text = " ".join(art["content"].split())
            excerpt = clean_text[:200] + "..." if len(clean_text) > 200 else clean_text
            ev = RetrievedEvidence(
                chunk_id=f"{art['id']}-lex",
                article_id=art["id"],
                article_title=art["title"],
                source_url=art["canonical_url"],
                heading=art.get("headings", [None])[0] if art.get("headings") else None,
                chunk_index=0,
                text=art["content"],
                score=score,
                excerpt=excerpt,
            )
            evidence.append(ev)

        top_score = evidence[0].score if evidence else None
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return RetrievalResult(
            evidence=evidence,
            citations=[e.to_citation() for e in evidence],
            top_score=top_score,
            sufficient_evidence=bool(top_score is not None and top_score > 0.3),
            retrieval_method="lexical_fallback",
            model_provider_used="none (lexical)",
            latency_ms=round(latency_ms, 2),
        )
