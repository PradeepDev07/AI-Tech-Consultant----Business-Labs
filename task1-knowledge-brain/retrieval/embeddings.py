"""Embedding provider interfaces and implementations."""

from abc import ABC, abstractmethod
import hashlib
import math
import httpx
from app.core.exceptions import ModelProviderError
from app.core.logging import logger


class BaseEmbeddingProvider(ABC):
    """Abstract interface for embedding generation."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate vector embedding for a single text string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a batch of text strings."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimension of generated embedding vectors."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the embedding provider."""
        pass


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic, zero-cost embedding double for testing and development environments."""

    def __init__(self, dim: int = 128):
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def provider_name(self) -> str:
        return "mock_development_provider"

    def embed_text(self, text: str) -> list[float]:
        """Generate a deterministic normalized vector based on weighted word and character tokens."""
        vec = [0.0] * self._dim
        clean = " ".join(text.lower().split())
        if not clean:
            return vec

        import re
        stopwords = {"how", "to", "do", "i", "a", "the", "on", "in", "is", "for", "with", "and", "your", "can", "of", "what"}
        words = re.findall(r"\w+", clean)

        for w in words:
            weight = 0.2 if w in stopwords else (1.0 + min(len(w), 8) * 0.3)
            h = int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            vec[idx] += weight

        # Also add character trigrams for subword robustness
        for i in range(max(1, len(clean) - 2)):
            tri = clean[i : i + 3]
            h = int(hashlib.md5(tri.encode("utf-8")).hexdigest(), 16)
            idx = (h >> 4) % self._dim
            vec[idx] += 0.15

        # Normalize to unit length
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Client for local/remote Ollama embedding endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        timeout_seconds: float = 15.0,
        dim: int = 768,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def provider_name(self) -> str:
        return f"ollama:{self.model}"

    def embed_text(self, text: str) -> list[float]:
        results = self.embed_batch([text])
        return results[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Call Ollama /api/embeddings for a batch of texts."""
        url = f"{self.base_url}/api/embeddings"
        embeddings: list[list[float]] = []

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                for text in texts:
                    payload = {"model": self.model, "prompt": text}
                    response = client.post(url, json=payload)
                    if response.status_code != 200:
                        raise ModelProviderError(
                            f"Ollama embedding error HTTP {response.status_code}: {response.text}"
                        )
                    data = response.json()
                    emb = data.get("embedding")
                    if not emb or not isinstance(emb, list):
                        raise ModelProviderError(
                            f"Invalid embedding returned by Ollama: {data}"
                        )
                    embeddings.append(emb)
            return embeddings
        except httpx.RequestError as exc:
            raise ModelProviderError(
                f"Failed to connect to Ollama embedding service at {self.base_url}: {exc}"
            ) from exc


def get_embedding_provider(
    provider_name: str = "mock",
    base_url: str = "http://localhost:11434",
    model: str = "nomic-embed-text",
) -> BaseEmbeddingProvider:
    """Factory creating the configured embedding provider."""
    if provider_name.lower() in ("mock", "dev", "test"):
        logger.info("Using MockEmbeddingProvider for deterministic test/development execution.")
        return MockEmbeddingProvider()
    elif provider_name.lower() == "ollama":
        return OllamaEmbeddingProvider(base_url=base_url, model=model)
    else:
        logger.warning(
            f"Unknown embedding provider '{provider_name}'. Falling back to MockEmbeddingProvider."
        )
        return MockEmbeddingProvider()
