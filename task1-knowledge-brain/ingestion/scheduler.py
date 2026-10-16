"""Ingestion scheduler orchestrating incremental updates, change detection, and vector re-indexing."""

import asyncio
from datetime import datetime, timezone
import uuid
from typing import Any
from app.core.exceptions import IngestionError
from app.core.logging import logger
from app.services.database import Database
from ingestion.change_detector import ChangeDetector
from ingestion.crawler import PoliteCrawler
from ingestion.parser import ArticleParser
from ingestion.sitemap import SitemapParser
from multimodal.image_processor import (
    ImageProcessingPipeline,
    NoneVisionProvider,
    create_vision_provider,
)
from retrieval.chunker import ArticleChunker
from retrieval.vector_store import BaseVectorStore


class IngestionPipeline:
    """Manages full and incremental ingestion cycles for Solution Center documentation."""

    def __init__(
        self,
        db: Database,
        vector_store: BaseVectorStore,
        sitemap_url: str = "https://support.brilliantdirectories.com/support/sitemap.xml",
        allowed_host: str = "support.brilliantdirectories.com",
        concurrency: int = 3,
        request_delay_seconds: float = 0.5,
        vision_pipeline: ImageProcessingPipeline | None = None,
    ):
        self.db = db
        self.vector_store = vector_store
        self.sitemap_url = sitemap_url
        self.allowed_host = allowed_host
        self.sitemap_parser = SitemapParser(allowed_host=allowed_host)
        self.crawler = PoliteCrawler(
            concurrency=concurrency,
            delay_seconds=request_delay_seconds,
        )
        self.article_parser = ArticleParser()
        self.chunker = ArticleChunker()
        self.change_detector = ChangeDetector(db=db)
        if vision_pipeline is not None:
            self.vision_pipeline = vision_pipeline
        else:
            try:
                from app.config import get_settings
                settings = get_settings()
                provider = create_vision_provider(settings)
                cache_dir = settings.resolve_image_cache_path()
            except Exception:
                provider = NoneVisionProvider()
                cache_dir = None
            self.vision_pipeline = ImageProcessingPipeline(vision_provider=provider, cache_dir=cache_dir)
        self._is_running = False

    async def run_incremental_job(
        self, force_refresh: bool = False, resume: bool = False
    ) -> dict[str, Any]:
        """Execute full incremental ingestion run with change detection, persistent queue, and cleanup."""
        if self._is_running:
            raise IngestionError("An ingestion job is already running. Overlapping runs are rejected.")

        self._is_running = True
        added_count = 0
        updated_count = 0
        unchanged_count = 0
        removed_count = 0
        errors: list[str] = []

        try:
            # Check for crash resumption if requested
            resumable = self.db.get_resumable_job() if resume else None
            if resumable:
                job_id = resumable["job_id"]
                logger.info(f"[{job_id}] Resuming interrupted ingestion job from persistent queue.")
                urls_to_fetch = self.db.get_pending_queue_urls(job_id)
                discovered_count = len(urls_to_fetch)
                plan = None
            else:
                job_id = f"job-{uuid.uuid4().hex[:8]}"
                self.db.create_ingestion_job(job_id)
                logger.info(f"[{job_id}] Starting ingestion job for {self.sitemap_url}")

                # 1. Discover URLs from sitemap
                discovered = await self.sitemap_parser.fetch_and_discover(self.sitemap_url)
                discovered_count = len(discovered)
                logger.info(f"[{job_id}] Discovered {discovered_count} URLs from sitemap.")

                # 2. Analyze changes against stored state
                plan = self.change_detector.analyze_sitemap(discovered)
                urls_to_fetch = list(plan.new_urls)
                if force_refresh:
                    urls_to_fetch.extend(plan.existing_urls_to_check)
                    urls_to_fetch.extend(plan.unchanged_urls)
                else:
                    urls_to_fetch.extend(plan.existing_urls_to_check)
                    unchanged_count += len(plan.unchanged_urls)

                logger.info(
                    f"[{job_id}] Change Plan: {len(plan.new_urls)} new, "
                    f"{len(plan.existing_urls_to_check)} check, "
                    f"{unchanged_count} unchanged, {len(plan.removed_urls)} removed"
                )

                # Initialize persistent queue cursor
                if urls_to_fetch:
                    self.db.init_ingestion_queue(job_id, urls_to_fetch)

            # 3. Crawl target URLs
            if urls_to_fetch:
                crawl_results = await self.crawler.crawl_batch(urls_to_fetch)
                for res in crawl_results:
                    if res.error or res.status_code != 200:
                        err_msg = f"Failed {res.url}: HTTP {res.status_code} ({res.error})"
                        errors.append(err_msg)
                        self.db.update_queue_item(job_id, res.url, "failed", err_msg)
                        logger.warning(err_msg)
                        continue

                    if res.not_modified:
                        unchanged_count += 1
                        self.db.update_queue_item(job_id, res.url, "completed")
                        continue

                    # Parse HTML
                    try:
                        parsed = self.article_parser.parse_html(res.content, res.url)
                    except Exception as exc:
                        err_msg = f"Parsing error for {res.url}: {exc}"
                        errors.append(err_msg)
                        self.db.update_queue_item(job_id, res.url, "failed", err_msg)
                        continue

                    # Check if existing article had identical content hash
                    existing = self.db.get_article_by_url(parsed["canonical_url"])
                    if existing and not force_refresh:
                        if not self.change_detector.is_content_changed(
                            existing["content_hash"], parsed["content_hash"]
                        ):
                            unchanged_count += 1
                            self.db.update_queue_item(job_id, res.url, "completed")
                            continue

                    # Save article
                    saved = self.db.upsert_article(parsed)
                    article_id = saved["id"]

                    # Remove existing chunks before re-indexing to avoid stale chunks
                    self.vector_store.delete_article_chunks(article_id)

                    # Generate text chunks & index
                    chunks = self.chunker.chunk_article(saved)
                    chunk_payloads = [
                        {
                            "chunk_id": c.chunk_id,
                            "text": c.text,
                            "metadata": c.metadata,
                        }
                        for c in chunks
                    ]

                    # Process screenshots if vision pipeline is available
                    screenshot_chunks = self.vision_pipeline.process_article_images(saved)
                    chunk_payloads.extend(screenshot_chunks)

                    if chunk_payloads:
                        self.vector_store.upsert_chunks(chunk_payloads)

                    if existing:
                        updated_count += 1
                    else:
                        added_count += 1

                    self.db.update_queue_item(job_id, res.url, "completed")

            # 4. Handle removed articles (only on full sitemap runs)
            if plan:
                for removed_url in plan.removed_urls:
                    existing = self.db.get_article_by_url(removed_url)
                    if existing:
                        art_id = existing["id"]
                        self.db.mark_article_deleted(art_id)
                        self.vector_store.delete_article_chunks(art_id)
                        removed_count += 1
                        logger.info(f"[{job_id}] Removed deleted article {art_id} ({removed_url})")

            status = "completed" if not errors else ("completed_with_errors" if (added_count or updated_count or unchanged_count) else "failed")
            self.db.update_ingestion_job(
                job_id=job_id,
                status=status,
                urls_discovered=discovered_count,
                articles_added=added_count,
                articles_updated=updated_count,
                articles_unchanged=unchanged_count,
                articles_removed=removed_count,
                errors=errors,
            )

            logger.info(
                f"[{job_id}] Finished: added={added_count}, updated={updated_count}, "
                f"unchanged={unchanged_count}, removed={removed_count}, errors={len(errors)}"
            )

            return {
                "job_id": job_id,
                "status": status,
                "urls_discovered": discovered_count,
                "articles_added": added_count,
                "articles_updated": updated_count,
                "articles_unchanged": unchanged_count,
                "articles_removed": removed_count,
                "errors": errors,
                "queue_summary": self.db.get_queue_summary(job_id),
            }

        except Exception as exc:
            logger.error(f"[{job_id}] Ingestion job failed fatally: {exc}")
            self.db.update_ingestion_job(
                job_id=job_id,
                status="failed",
                errors=[str(exc)],
            )
            raise
        finally:
            self._is_running = False


class PeriodicIngestionWorker:
    """Non-blocking background worker executing periodic incremental ingestion."""

    def __init__(
        self,
        pipeline: IngestionPipeline | None = None,
        interval_hours: float = 24.0,
        job_runner: Any = None,
    ):
        self.pipeline = pipeline
        self.job_runner = job_runner or (pipeline.run_incremental_job if pipeline else None)
        self.interval_seconds = max(0.01, interval_hours * 3600.0)
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Run the periodic ingestion loop."""
        self._running = True
        logger.info(
            f"Periodic ingestion worker started (interval: {self.interval_seconds / 3600.0:.4f}h)."
        )
        while self._running:
            try:
                await asyncio.sleep(self.interval_seconds)
                if not self._running:
                    break
                logger.info("Periodic timer triggered: running incremental ingestion.")
                if self.job_runner:
                    await self.job_runner()
            except asyncio.CancelledError:
                logger.info("Periodic ingestion worker cancelled.")
                break
            except Exception as exc:
                logger.error(f"Error during scheduled ingestion run: {exc}")

    async def stop(self) -> None:
        """Signal the periodic worker to stop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
