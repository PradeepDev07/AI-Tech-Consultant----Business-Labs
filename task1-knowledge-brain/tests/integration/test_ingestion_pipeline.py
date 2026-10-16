"""Integration tests for the full ingestion pipeline: sitemap discovery -> polite crawl -> parse -> vector index -> change detection -> deletion."""

import tempfile
import httpx
import pytest
from app.services.database import Database
from ingestion.crawler import PoliteCrawler
from ingestion.scheduler import IngestionPipeline
from ingestion.sitemap import SitemapParser
from retrieval.embeddings import MockEmbeddingProvider
from retrieval.vector_store import InMemoryVectorStore

SAMPLE_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://support.brilliantdirectories.com/article/1</loc>
    <lastmod>2026-03-01T00:00:00Z</lastmod>
  </url>
  <url>
    <loc>https://support.brilliantdirectories.com/article/2</loc>
    <lastmod>2026-03-01T00:00:00Z</lastmod>
  </url>
</urlset>
"""

SAMPLE_ARTICLE_1_HTML = """<!DOCTYPE html>
<html>
<head><title>Stripe Setup Guide</title></head>
<body>
  <article>
    <h1>Stripe Setup Guide</h1>
    <p>To configure Stripe, enter your Publishable Key and Secret Key in Finance > Payment Settings.</p>
  </article>
</body>
</html>
"""

SAMPLE_ARTICLE_2_HTML = """<!DOCTYPE html>
<html>
<head><title>Member Categories</title></head>
<body>
  <article>
    <h1>Member Categories</h1>
    <p>Organize members into top-level and sub-level categories under My Members > Member Categories.</p>
  </article>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_full_and_incremental_ingestion_cycle():
    """Verify full ingestion cycle, incremental non-reprocessing, and removed article cleanup."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp_db:
        db = Database(tmp_db.name)
        embeddings = MockEmbeddingProvider(dim=64)
        vector_store = InMemoryVectorStore(embedding_provider=embeddings)

        current_sitemap = SAMPLE_SITEMAP_XML

        def mock_transport_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "sitemap.xml" in url_str:
                return httpx.Response(200, text=current_sitemap)
            elif "article/1" in url_str:
                return httpx.Response(200, text=SAMPLE_ARTICLE_1_HTML)
            elif "article/2" in url_str:
                return httpx.Response(200, text=SAMPLE_ARTICLE_2_HTML)
            return httpx.Response(404, text="Not Found")

        transport = httpx.MockTransport(mock_transport_handler)
        mock_client = httpx.AsyncClient(transport=transport)

        pipeline = IngestionPipeline(
            db=db,
            vector_store=vector_store,
            sitemap_url="https://support.brilliantdirectories.com/support/sitemap.xml",
            request_delay_seconds=0.0,
        )

        # Patch sitemap parser and crawler client to use mock transport
        orig_sitemap_fetch = pipeline.sitemap_parser.fetch_and_discover
        pipeline.sitemap_parser.fetch_and_discover = lambda url: orig_sitemap_fetch(url, client=mock_client)
        pipeline.crawler.crawl_batch = lambda urls, **kw: PoliteCrawler(
            concurrency=2, delay_seconds=0.0
        ).crawl_batch(urls, client=mock_client)

        # --- Cycle 1: Initial Ingestion ---
        res1 = await pipeline.run_incremental_job()
        assert res1["status"] == "completed"
        assert res1["articles_added"] == 2
        assert res1["articles_updated"] == 0
        assert res1["articles_unchanged"] == 0
        assert res1["articles_removed"] == 0
        assert vector_store.count() >= 2

        # Check DB records
        articles, total = db.list_articles()
        assert total == 2

        # --- Cycle 2: Incremental Run (Nothing Changed) ---
        res2 = await pipeline.run_incremental_job()
        assert res2["status"] == "completed"
        assert res2["articles_added"] == 0
        assert res2["articles_updated"] == 0
        assert res2["articles_unchanged"] == 2
        assert res2["articles_removed"] == 0

        # --- Cycle 3: Article 2 removed from sitemap ---
        current_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://support.brilliantdirectories.com/article/1</loc>
            <lastmod>2026-03-01T00:00:00Z</lastmod>
          </url>
        </urlset>
        """

        res3 = await pipeline.run_incremental_job()
        assert res3["status"] == "completed"
        assert res3["articles_removed"] == 1
        assert res3["articles_unchanged"] == 1

        # Article 2 is soft-deleted in DB
        art2 = db.get_article_by_url("https://support.brilliantdirectories.com/article/2")
        assert art2["is_deleted"] is True
        assert art2["status"] == "removed"

        # Article 2 chunks purged from vector store
        for item in vector_store._chunks.values():
            assert item["metadata"]["article_id"] != art2["id"]
