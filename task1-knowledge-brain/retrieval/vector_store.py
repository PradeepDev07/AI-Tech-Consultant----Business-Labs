"""Vector store abstractions and adapters for ChromaDB and development fallback."""

from abc import ABC, abstractmethod
import math
from pathlib import Path
from typing import Any
from app.core.exceptions import VectorStoreError
from app.core.logging import logger
from retrieval.embeddings import BaseEmbeddingProvider


class BaseVectorStore(ABC):
    """Abstract interface for storing and retrieving embedded chunks."""

    @abstractmethod
    def upsert_chunks(
        self,
        chunks: list[dict[str, Any]],
        embedding_provider: BaseEmbeddingProvider | None = None,
    ) -> None:
        """Upsert text chunks with embeddings and metadata into the vector index."""
        pass

    @abstractmethod
    def query(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        where_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query nearest chunks by cosine similarity."""
        pass

    @abstractmethod
    def delete_article_chunks(self, article_id: str) -> None:
        """Delete all chunks associated with an article."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Return total number of indexed chunks."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Clear all indexed data."""
        pass


class InMemoryVectorStore(BaseVectorStore):
    """Clean in-memory vector store adapter using cosine similarity.

    Used in development and test environments when ChromaDB is unavailable or mock mode is requested.
    """

    def __init__(self, embedding_provider: BaseEmbeddingProvider | None = None):
        self.embedding_provider = embedding_provider
        self._chunks: dict[str, dict[str, Any]] = {}  # chunk_id -> chunk dict

    def upsert_chunks(
        self,
        chunks: list[dict[str, Any]],
        embedding_provider: BaseEmbeddingProvider | None = None,
    ) -> None:
        provider = embedding_provider or self.embedding_provider
        for chunk in chunks:
            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            embedding = chunk.get("embedding")
            if embedding is None:
                if provider is None:
                    raise VectorStoreError(
                        "Embedding provider required to generate chunk embeddings."
                    )
                embedding = provider.embed_text(text)

            self._chunks[chunk_id] = {
                "chunk_id": chunk_id,
                "text": text,
                "metadata": chunk.get("metadata", {}),
                "embedding": embedding,
            }

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        where_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self._chunks or not query_embedding:
            return []

        scored_results: list[tuple[float, dict[str, Any]]] = []

        for item in self._chunks.values():
            meta = item["metadata"]
            if where_filter:
                match = True
                for k, v in where_filter.items():
                    if meta.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            # Compute cosine similarity
            emb = item["embedding"]
            score = self._cosine_similarity(query_embedding, emb)
            scored_results.append((score, item))

        # Sort descending by score
        scored_results.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, item in scored_results[:top_k]:
            results.append(
                {
                    "chunk_id": item["chunk_id"],
                    "text": item["text"],
                    "metadata": item["metadata"],
                    "score": score,
                }
            )
        return results

    def delete_article_chunks(self, article_id: str) -> None:
        to_delete = [
            cid
            for cid, item in self._chunks.items()
            if item["metadata"].get("article_id") == article_id
        ]
        for cid in to_delete:
            del self._chunks[cid]

    def count(self) -> int:
        return len(self._chunks)

    def reset(self) -> None:
        self._chunks.clear()

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)


class ChromaVectorStore(BaseVectorStore):
    """Vector store adapter backed by ChromaDB persistent storage."""

    def __init__(
        self,
        persist_dir: str,
        collection_name: str = "knowledge_brain_articles",
        embedding_provider: BaseEmbeddingProvider | None = None,
    ):
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError as e:
            raise VectorStoreError(f"ChromaDB is not installed in the environment: {e}") from e

        self.persist_dir = persist_dir
        self.embedding_provider = embedding_provider
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        try:
            self.client = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            raise VectorStoreError(f"Failed to initialize ChromaDB collection: {e}") from e

    def upsert_chunks(
        self,
        chunks: list[dict[str, Any]],
        embedding_provider: BaseEmbeddingProvider | None = None,
    ) -> None:
        if not chunks:
            return

        provider = embedding_provider or self.embedding_provider
        ids = []
        documents = []
        metadatas = []
        embeddings = []

        for chunk in chunks:
            ids.append(chunk["chunk_id"])
            documents.append(chunk["text"])
            # Flatten or stringify complex metadata values for Chroma compatibility
            clean_meta = {}
            for k, v in chunk.get("metadata", {}).items():
                if v is None:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)
            metadatas.append(clean_meta)

            emb = chunk.get("embedding")
            if emb is None:
                if provider is None:
                    raise VectorStoreError(
                        "Embedding provider required to generate chunk embeddings."
                    )
                emb = provider.embed_text(chunk["text"])
            embeddings.append(emb)

        try:
            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as e:
            raise VectorStoreError(f"ChromaDB upsert failed: {e}") from e

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 4,
        where_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            kwargs: dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "include": ["documents", "metadatas", "distances"],
            }
            if where_filter:
                kwargs["where"] = where_filter

            res = self.collection.query(**kwargs)
            if not res or not res.get("ids") or not res["ids"][0]:
                return []

            matched = []
            ids = res["ids"][0]
            docs = res["documents"][0]
            metas = res["metadatas"][0]
            # Chroma returns cosine distance (0 = identical, 2 = opposite)
            # Similarity = 1 - distance
            distances = res.get("distances", [[0.0] * len(ids)])[0]

            for cid, doc, meta, dist in zip(ids, docs, metas, distances):
                similarity = max(0.0, min(1.0, 1.0 - dist))
                matched.append(
                    {
                        "chunk_id": cid,
                        "text": doc,
                        "metadata": meta,
                        "score": similarity,
                    }
                )
            return matched
        except Exception as e:
            raise VectorStoreError(f"ChromaDB query failed: {e}") from e

    def delete_article_chunks(self, article_id: str) -> None:
        try:
            self.collection.delete(where={"article_id": article_id})
        except Exception as e:
            raise VectorStoreError(f"ChromaDB delete failed: {e}") from e

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection.name)
            self.collection = self.client.get_or_create_collection(
                name="knowledge_brain_articles",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            raise VectorStoreError(f"ChromaDB reset failed: {e}") from e


def create_vector_store(
    persist_dir: str,
    provider_type: str = "auto",
    embedding_provider: BaseEmbeddingProvider | None = None,
) -> BaseVectorStore:
    """Factory creating vector store with automatic fallback if ChromaDB is unavailable."""
    if provider_type.lower() == "in_memory":
        logger.info("Using InMemoryVectorStore as requested.")
        return InMemoryVectorStore(embedding_provider=embedding_provider)

    try:
        import chromadb  # noqa: F401
        logger.info(f"Initializing ChromaVectorStore at {persist_dir}")
        return ChromaVectorStore(
            persist_dir=persist_dir,
            embedding_provider=embedding_provider,
        )
    except Exception as exc:
        logger.warning(
            f"ChromaDB unavailable ({exc}). Using InMemoryVectorStore as fallback."
        )
        return InMemoryVectorStore(embedding_provider=embedding_provider)
