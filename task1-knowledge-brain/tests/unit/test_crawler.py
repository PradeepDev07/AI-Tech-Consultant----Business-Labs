"""Unit tests for asynchronous polite crawler using httpx mock transport."""

import httpx
import pytest
from ingestion.crawler import PoliteCrawler


@pytest.mark.asyncio
async def test_crawler_success():
    """Verify crawler successfully fetches page content."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>Article Content</body></html>", headers={"etag": "abc-123"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        crawler = PoliteCrawler(concurrency=2, delay_seconds=0.0)
        result = await crawler.fetch_page("https://support.brilliantdirectories.com/article/1", client=client)

    assert result.status_code == 200
    assert result.content == "<html><body>Article Content</body></html>"
    assert result.etag == "abc-123"
    assert result.not_modified is False


@pytest.mark.asyncio
async def test_crawler_304_not_modified():
    """Verify crawler handles 304 Not Modified without downloading body."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("if-none-match") == "cached-etag":
            return httpx.Response(304, headers={"etag": "cached-etag"})
        return httpx.Response(200, text="New Content")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        crawler = PoliteCrawler(concurrency=1, delay_seconds=0.0)
        result = await crawler.fetch_page(
            "https://support.brilliantdirectories.com/article/1",
            client=client,
            etag="cached-etag",
        )

    assert result.status_code == 304
    assert result.not_modified is True
    assert result.content is None


@pytest.mark.asyncio
async def test_crawler_retry_transient_error():
    """Verify crawler retries on 500 and succeeds when server recovers."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, text="Internal Server Error")
        return httpx.Response(200, text="Recovered Content")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        crawler = PoliteCrawler(concurrency=1, delay_seconds=0.0, backoff_factor=0.01)
        result = await crawler.fetch_page(
            "https://support.brilliantdirectories.com/article/1", client=client
        )

    assert result.status_code == 200
    assert result.content == "Recovered Content"
    assert attempts == 2
