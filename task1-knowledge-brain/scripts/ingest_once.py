#!/usr/bin/env python3
"""Run a single manual or scheduled ingestion run against Brilliant Directories Solution Center."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.core.logging import logger
from app.services.database import Database
from ingestion.scheduler import IngestionPipeline
from multimodal.image_processor import ImageProcessingPipeline, create_vision_provider
from retrieval.embeddings import get_embedding_provider
from retrieval.vector_store import create_vector_store


async def main():
    parser = argparse.ArgumentParser(description="Ingest Brilliant Directories Solution Center articles.")
    parser.add_argument("--force", action="store_true", help="Force re-fetching and re-indexing all articles")
    args = parser.parse_args()

    settings = get_settings()
    logger.info("Initializing Ingestion Script...")

    db = Database(str(settings.resolve_sqlite_path()))
    embeddings = get_embedding_provider(
        provider_name=settings.embedding_provider,
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )
    vector_store = create_vector_store(
        persist_dir=str(settings.resolve_chroma_path()),
        embedding_provider=embeddings,
    )

    # Configure vision pipeline
    vision_provider = create_vision_provider(settings)
    vision_pipeline = ImageProcessingPipeline(
        vision_provider=vision_provider,
        cache_dir=settings.resolve_image_cache_path(),
    )

    pipeline = IngestionPipeline(
        db=db,
        vector_store=vector_store,
        sitemap_url=settings.sitemap_url,
        concurrency=settings.crawler_concurrency,
        request_delay_seconds=settings.crawler_request_delay_seconds,
        vision_pipeline=vision_pipeline,
    )

    logger.info(f"Starting ingestion run (force={args.force})...")
    result = await pipeline.run_incremental_job(force_refresh=args.force)

    logger.info("=" * 60)
    logger.info(f"Ingestion Finished: Job ID {result['job_id']}")
    logger.info(f"Status:             {result['status']}")
    logger.info(f"URLs Discovered:    {result['urls_discovered']}")
    logger.info(f"Articles Added:     {result['articles_added']}")
    logger.info(f"Articles Updated:   {result['articles_updated']}")
    logger.info(f"Articles Unchanged: {result['articles_unchanged']}")
    logger.info(f"Articles Removed:   {result['articles_removed']}")
    logger.info(f"Errors Encountered: {len(result['errors'])}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
