"""Asynchronous polite web crawler with concurrency bounds, retries, and rate limiting."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import httpx
from app.core.exceptions import CrawlerError
from app.core.logging import logger


@dataclass
class CrawlResult:
    """Outcome of crawling a single URL."""

    url: str
    status_code: int
    content: str | None = None
    not_modified: bool = False
    etag: str | None = None
    last_modified: str | None = None
    fetch_time_ms: float = 0.0
    error: str | None = None


class PoliteCrawler:
    """Asynchronous HTTP crawler adhering to politeness, concurrency, and retry guidelines."""

    def __init__(
        self,
        concurrency: int = 3,
        delay_seconds: float = 0.5,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        user_agent: str = "KnowledgeBrainBot/1.0 (+https://support.brilliantdirectories.com)",
    ):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.user_agent = user_agent

    async def fetch_page(
        self,
        url: str,
        client: httpx.AsyncClient,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> CrawlResult:
        """Fetch a single URL with polite pacing, retries, and conditional headers."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        async with self.semaphore:
            # Politeness delay
            if self.delay_seconds > 0:
                await asyncio.sleep(self.delay_seconds)

            attempt = 0
            while attempt < self.max_retries:
                attempt += 1
                start_time = asyncio.get_event_loop().time()
                try:
                    logger.debug(f"Crawling {url} (attempt {attempt}/{self.max_retries})")
                    response = await client.get(url, headers=headers)
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                    # 304 Not Modified
                    if response.status_code == 304:
                        return CrawlResult(
                            url=url,
                            status_code=304,
                            not_modified=True,
                            etag=response.headers.get("etag") or etag,
                            last_modified=response.headers.get("last-modified") or last_modified,
                            fetch_time_ms=duration_ms,
                        )

                    # 429 Too Many Requests or 503 Service Unavailable -> respect Retry-After
                    if response.status_code in (429, 503):
                        retry_after_str = response.headers.get("Retry-After")
                        wait_seconds = 2.0
                        if retry_after_str:
                            try:
                                wait_seconds = float(retry_after_str)
                            except ValueError:
                                wait_seconds = 2.0
                        logger.warning(
                            f"Received HTTP {response.status_code} for {url}. Backing off {wait_seconds:.1f}s"
                        )
                        await asyncio.sleep(wait_seconds)
                        continue

                    # Server errors -> exponential backoff
                    if response.status_code >= 500:
                        wait = self.backoff_factor ** attempt
                        logger.warning(
                            f"HTTP {response.status_code} on {url}. Retrying in {wait:.1f}s..."
                        )
                        await asyncio.sleep(wait)
                        continue

                    response.raise_for_status()

                    return CrawlResult(
                        url=url,
                        status_code=response.status_code,
                        content=response.text,
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        fetch_time_ms=duration_ms,
                    )

                except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
                    wait = self.backoff_factor ** attempt
                    logger.warning(
                        f"Transient error fetching {url}: {exc}. Retrying in {wait:.1f}s"
                    )
                    if attempt >= self.max_retries:
                        return CrawlResult(
                            url=url,
                            status_code=0,
                            error=f"Timeout/Connection failed after {self.max_retries} attempts: {exc}",
                        )
                    await asyncio.sleep(wait)

                except httpx.HTTPStatusError as exc:
                    # Client errors (404, 403, etc.) - don't retry indefinitely
                    return CrawlResult(
                        url=url,
                        status_code=exc.response.status_code,
                        error=f"HTTP Status Error: {exc}",
                    )

                except Exception as exc:
                    return CrawlResult(
                        url=url,
                        status_code=0,
                        error=f"Unexpected error crawling {url}: {exc}",
                    )

            return CrawlResult(
                url=url,
                status_code=0,
                error=f"Exhausted {self.max_retries} retries for {url}",
            )

    async def crawl_batch(
        self,
        urls: list[str],
        client: httpx.AsyncClient | None = None,
        url_metadata_lookup: dict[str, dict[str, Any]] | None = None,
    ) -> list[CrawlResult]:
        """Crawl a collection of URLs with bounded concurrency."""
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout_seconds)
            close_client = True

        tasks = []
        lookup = url_metadata_lookup or {}
        for url in urls:
            meta = lookup.get(url, {})
            tasks.append(
                self.fetch_page(
                    url=url,
                    client=client,
                    etag=meta.get("etag"),
                    last_modified=meta.get("last_modified"),
                )
            )

        try:
            return await asyncio.gather(*tasks)
        finally:
            if close_client:
                await client.aclose()
