"""HTTP client for Task 1 Knowledge Brain grounded answering API."""

import asyncio
import random
import time
from typing import Any
import httpx
from pydantic import BaseModel
from app.schemas import Citation


class KnowledgeLookupResult(BaseModel):
    """Structured lookup response from Task 1 Knowledge Brain."""

    success: bool
    abstained: bool = False
    abstention_reason: str | None = None
    answer: str = ""
    citations: list[Citation] = []
    error: str | None = None
    latency_ms: float = 0.0


class KnowledgeBrainClient:
    """Dedicated, resilient HTTP client querying Task 1 Knowledge Brain."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        base_delay_seconds: float = 0.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds

    async def query_knowledge(
        self,
        question: str,
        top_k: int = 4,
        min_threshold: float = 0.35,
    ) -> KnowledgeLookupResult:
        """Query Task 1 Knowledge Brain with bounded retries and exponential backoff."""
        start_time = time.time()
        endpoint = f"{self.base_url}/api/v1/questions"

        payload = {
            "question": question.strip(),
            "top_k": top_k,
            "min_evidence_threshold": min_threshold,
        }

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        attempt = 0
        last_error = ""

        while attempt < self.max_retries:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)

                    # 1. Success (200 OK)
                    if response.status_code == 200:
                        data = response.json()
                        latency_ms = (time.time() - start_time) * 1000

                        citations = [
                            Citation(
                                article_id=c.get("article_id", "unknown"),
                                article_title=c.get("article_title", "Untitled"),
                                source_url=c.get("source_url", ""),
                                heading=c.get("heading"),
                                chunk_index=c.get("chunk_index"),
                                excerpt=c.get("excerpt", ""),
                                relevance_score=c.get("relevance_score"),
                            )
                            for c in data.get("citations", [])
                        ]

                        return KnowledgeLookupResult(
                            success=True,
                            abstained=data.get("abstained", False),
                            abstention_reason=data.get("abstention_reason"),
                            answer=data.get("answer", ""),
                            citations=citations,
                            latency_ms=latency_ms,
                        )

                    # 2. Client Errors (400, 401, 403, 404, 422) - do not retry repeatedly
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        latency_ms = (time.time() - start_time) * 1000
                        return KnowledgeLookupResult(
                            success=False,
                            abstained=True,
                            abstention_reason=f"Task 1 rejected request with HTTP {response.status_code}",
                            error=f"Client error HTTP {response.status_code}: {response.text}",
                            latency_ms=latency_ms,
                        )

                    # 3. Server Errors (5xx) or Rate Limits (429) -> Backoff with jitter
                    retry_after = response.headers.get("retry-after")
                    delay = self._calculate_backoff(attempt)
                    if retry_after:
                        try:
                            delay = min(float(retry_after), 10.0)
                        except ValueError:
                            pass

                    last_error = f"Task 1 returned HTTP {response.status_code} on attempt {attempt}"
                    if attempt < self.max_retries:
                        await asyncio.sleep(delay)

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = f"Task 1 network error on attempt {attempt}: {str(exc)}"
                if attempt < self.max_retries:
                    delay = self._calculate_backoff(attempt)
                    await asyncio.sleep(delay)

        # Retries exhausted
        latency_ms = (time.time() - start_time) * 1000
        return KnowledgeLookupResult(
            success=False,
            abstained=True,
            abstention_reason="Task 1 Knowledge Brain unavailable after retries.",
            error=last_error or "Unknown failure querying Task 1",
            latency_ms=latency_ms,
        )

    def _calculate_backoff(self, attempt: int) -> float:
        exponential = self.base_delay_seconds * (2 ** (attempt - 1))
        jitter = random.uniform(0, self.base_delay_seconds / 2)
        return min(exponential + jitter, 5.0)
