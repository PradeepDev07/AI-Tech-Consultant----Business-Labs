"""Unit tests for in-process PeriodicIngestionWorker and background scheduler."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from ingestion.scheduler import PeriodicIngestionWorker


@pytest.mark.asyncio
async def test_periodic_worker_lifecycle():
    """Verify PeriodicIngestionWorker starts, triggers runner, and stops cleanly."""
    mock_runner = AsyncMock(return_value={"status": "completed"})

    worker = PeriodicIngestionWorker(
        job_runner=mock_runner,
        interval_hours=0.00001,  # ~0.036 seconds
    )
    assert worker.is_running is False

    task = asyncio.create_task(worker.start())
    worker._task = task
    await asyncio.sleep(0.01)
    assert worker.is_running is True

    # Allow worker loop to run at least one tick
    await asyncio.sleep(0.08)

    await worker.stop()
    assert worker.is_running is False
    assert mock_runner.call_count >= 1


@pytest.mark.asyncio
async def test_periodic_worker_error_resilience():
    """Verify PeriodicIngestionWorker catches exceptions in runner without crashing the loop."""
    mock_runner = AsyncMock(side_effect=[RuntimeError("Temporary Network Glitch"), {"status": "completed"}])

    worker = PeriodicIngestionWorker(
        job_runner=mock_runner,
        interval_hours=0.00001,
    )

    task = asyncio.create_task(worker.start())
    worker._task = task
    await asyncio.sleep(0.08)
    await worker.stop()

    assert worker.is_running is False
    assert mock_runner.call_count >= 1


@pytest.mark.asyncio
async def test_app_lifespan_background_worker():
    """Verify FastAPI lifespan starts worker when enabled and stops it on teardown."""
    from app.main import app, lifespan

    with patch("app.main.get_settings") as mock_settings:
        mock_settings.return_value.scheduled_ingestion_enabled = True
        mock_settings.return_value.scheduled_ingestion_interval_hours = 24.0
        mock_settings.return_value.sitemap_url = "https://example.com/sitemap.xml"
        mock_settings.return_value.crawler_concurrency = 1
        mock_settings.return_value.crawler_request_delay_seconds = 0.1

        with patch("app.dependencies.get_database"):
            with patch("app.dependencies.get_vector_store_instance"):
                with patch("ingestion.scheduler.PeriodicIngestionWorker.start", new_callable=AsyncMock) as mock_start:
                    with patch("ingestion.scheduler.PeriodicIngestionWorker.stop", new_callable=AsyncMock) as mock_stop:
                        async with lifespan(app):
                            mock_start.assert_called_once()
                        mock_stop.assert_called_once()
