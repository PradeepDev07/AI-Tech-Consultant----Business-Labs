"""Unit tests for embeddings, vector store adapters, retrieval, citation, and abstention."""

import tempfile
from app.services.database import Database
from retrieval.embeddings import MockEmbeddingProvider
from retrieval.retriever import Retriever
from retrieval.vector_store import InMemoryVectorStore


def test_mock_embedding_provider():
    """Verify mock embedding provider generates deterministic unit vectors."""
    provider = MockEmbeddingProvider(dim=32)
    vec1 = provider.embed_text("How to configure Stripe?")
    vec2 = provider.embed_text("How to configure Stripe?")
    vec3 = provider.embed_text("Completely unrelated topic about gardening.")

    assert len(vec1) == 32
    assert vec1 == vec2  # Deterministic
    # Dot product of identical vectors is 1.0 (unit vector)
    dot_identical = sum(a * b for a, b in zip(vec1, vec2))
    assert abs(dot_identical - 1.0) < 1e-4

    # Dot product of unrelated texts is much lower
    dot_unrelated = sum(a * b for a, b in zip(vec1, vec3))
    assert dot_unrelated < dot_identical


def test_retriever_evidence_and_citation():
    """Verify retriever retrieves relevant chunks and constructs accurate citations."""
    provider = MockEmbeddingProvider(dim=32)
    store = InMemoryVectorStore(embedding_provider=provider)

    chunks = [
        {
            "chunk_id": "art-1-c0",
            "text": "Brilliant Directories integrates with Stripe for member payments.",
            "metadata": {
                "article_id": "art-1",
                "title": "Stripe Integration",
                "source_url": "https://support.brilliantdirectories.com/stripe",
                "heading": "Overview",
                "chunk_index": 0,
            },
        },
        {
            "chunk_id": "art-2-c0",
            "text": "How to customize CSS styles on your directory website.",
            "metadata": {
                "article_id": "art-2",
                "title": "Custom CSS",
                "source_url": "https://support.brilliantdirectories.com/css",
                "heading": "Styling",
                "chunk_index": 0,
            },
        },
    ]
    store.upsert_chunks(chunks)

    retriever = Retriever(
        vector_store=store,
        embedding_provider=provider,
        default_top_k=2,
        min_evidence_threshold=0.3,
    )

    res = retriever.retrieve("How do I connect Stripe?")
    assert len(res.evidence) > 0
    assert res.evidence[0].article_id == "art-1"
    assert res.evidence[0].article_title == "Stripe Integration"
    assert res.sufficient_evidence is True
    assert len(res.citations) > 0
    citation = res.citations[0]
    assert citation.article_id == "art-1"
    assert citation.source_url == "https://support.brilliantdirectories.com/stripe"
    assert citation.relevance_score is not None


def test_retriever_deleted_source_filtering():
    """Verify retriever discards chunks belonging to deleted articles."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db = Database(tmp.name)

        # Create active article in DB
        db.upsert_article({
            "id": "art-del",
            "canonical_url": "https://support.brilliantdirectories.com/deleted-page",
            "title": "Legacy Feature",
            "content": "This feature has been removed.",
            "content_hash": "hdel",
            "status": "active",
        })

        provider = MockEmbeddingProvider(dim=32)
        store = InMemoryVectorStore(embedding_provider=provider)
        store.upsert_chunks([
            {
                "chunk_id": "art-del-c0",
                "text": "This feature has been removed from Brilliant Directories.",
                "metadata": {
                    "article_id": "art-del",
                    "title": "Legacy Feature",
                    "source_url": "https://support.brilliantdirectories.com/deleted-page",
                },
            }
        ])

        retriever = Retriever(vector_store=store, embedding_provider=provider, db=db)

        # Before deletion: chunk is returned
        before_res = retriever.retrieve("feature")
        assert len(before_res.evidence) == 1

        # Soft delete the article in DB
        db.mark_article_deleted("art-del")

        # After deletion: chunk must be filtered out!
        after_res = retriever.retrieve("feature")
        assert len(after_res.evidence) == 0
        assert after_res.sufficient_evidence is False


def test_retriever_abstention_on_weak_evidence():
    """Verify retriever flags sufficient_evidence=False when relevance is below threshold."""
    provider = MockEmbeddingProvider(dim=32)
    store = InMemoryVectorStore(embedding_provider=provider)

    store.upsert_chunks([
        {
            "chunk_id": "art-ssl-c0",
            "text": "SSL certificates can be purchased from your domain registrar.",
            "metadata": {
                "article_id": "art-ssl",
                "title": "SSL Setup",
                "source_url": "https://support.brilliantdirectories.com/ssl",
            },
        }
    ])

    retriever = Retriever(
        vector_store=store,
        embedding_provider=provider,
        min_evidence_threshold=0.99,  # Impossibly high threshold
    )

    res = retriever.retrieve("What is quantum computing?")
    assert res.sufficient_evidence is False
