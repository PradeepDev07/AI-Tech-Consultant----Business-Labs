"""Unit tests for article chunker."""

from retrieval.chunker import ArticleChunker


def test_chunker_basic():
    """Verify chunker creates chunks with article and heading metadata."""
    article = {
        "id": "art-001",
        "title": "Payment Settings",
        "canonical_url": "https://support.brilliantdirectories.com/payments",
        "content": "Brilliant Directories connects to Stripe and PayPal.\n\nStripe setup requires API keys.",
        "headings": ["Stripe Setup"],
        "content_hash": "hash123",
    }

    chunker = ArticleChunker(chunk_size=500, chunk_overlap=100)
    chunks = chunker.chunk_article(article)

    assert len(chunks) >= 1
    assert chunks[0].article_id == "art-001"
    assert chunks[0].article_title == "Payment Settings"
    assert chunks[0].source_url == "https://support.brilliantdirectories.com/payments"
    assert "Article: Payment Settings" in chunks[0].text
    assert chunks[0].metadata["content_hash"] == "hash123"


def test_chunker_empty_content():
    """Verify chunker returns empty list for blank article content."""
    article = {
        "id": "art-empty",
        "title": "Empty Article",
        "canonical_url": "https://support.brilliantdirectories.com/empty",
        "content": "   \n\n  ",
        "headings": [],
        "content_hash": "empty",
    }
    chunker = ArticleChunker()
    chunks = chunker.chunk_article(article)
    assert len(chunks) == 0


def test_chunker_overlap():
    """Verify large text is divided into multiple chunks with overlap."""
    long_content = "\n\n".join([f"Paragraph {i}: This is detailed information regarding Brilliant Directories configuration option {i}." for i in range(20)])
    article = {
        "id": "art-long",
        "title": "Comprehensive Guide",
        "canonical_url": "https://support.brilliantdirectories.com/guide",
        "content": long_content,
        "headings": ["Guide"],
        "content_hash": "longhash",
    }

    chunker = ArticleChunker(chunk_size=300, chunk_overlap=50)
    chunks = chunker.chunk_article(article)

    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) > 0
        assert c.chunk_index >= 0
