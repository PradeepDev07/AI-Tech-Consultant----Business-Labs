#!/usr/bin/env python3
"""Seed the default Knowledge Brain database and Chroma vector store with reference documentation."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.core.logging import logger
from app.services.database import Database
from evaluation.runner import seed_evaluation_knowledge
from retrieval.chunker import ArticleChunker
from retrieval.embeddings import get_embedding_provider
from retrieval.vector_store import create_vector_store


def seed():
    settings = get_settings()
    logger.info("Initializing Seed Script for Task 1 Knowledge Brain...")

    db_path = settings.resolve_sqlite_path()
    chroma_path = settings.resolve_chroma_path()

    logger.info(f"Target SQLite: {db_path}")
    logger.info(f"Target Chroma: {chroma_path}")

    db = Database(str(db_path))
    embeddings = get_embedding_provider(
        provider_name=settings.embedding_provider,
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )
    vector_store = create_vector_store(
        persist_dir=str(chroma_path),
        embedding_provider=embeddings,
    )
    chunker = ArticleChunker(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)

    seed_evaluation_knowledge(db=db, vector_store=vector_store, chunker=chunker)
    logger.info("Knowledge Brain database and Chroma vector store successfully seeded!")


if __name__ == "__main__":
    seed()
