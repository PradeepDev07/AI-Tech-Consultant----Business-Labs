"""Unit tests for persistent SQLite ingestion queue cursor and crash resumption."""

import tempfile
import pytest
from app.services.database import Database


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for isolated test execution."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db = Database(tmp.name)
        yield db


def test_ingestion_queue_initialization(temp_db):
    """Verify ingestion queue initializes and tracks URLs cleanly."""
    job_id = "job-queue-001"
    urls = [
        "https://support.brilliantdirectories.com/article/1",
        "https://support.brilliantdirectories.com/article/2",
        "https://support.brilliantdirectories.com/article/3",
    ]

    count = temp_db.init_ingestion_queue(job_id=job_id, urls=urls)
    assert count == 3

    pending = temp_db.get_pending_queue_urls(job_id=job_id)
    assert len(pending) == 3
    assert set(pending) == set(urls)

    summary = temp_db.get_queue_summary(job_id=job_id)
    assert summary["total"] == 3
    assert summary["pending"] == 3
    assert summary["processing"] == 0
    assert summary["completed"] == 0
    assert summary["failed"] == 0


def test_ingestion_queue_state_transitions(temp_db):
    """Verify queue status transitions through processing, completed, and failed."""
    job_id = "job-queue-002"
    url1 = "https://support.brilliantdirectories.com/article/success"
    url2 = "https://support.brilliantdirectories.com/article/fail"

    temp_db.init_ingestion_queue(job_id=job_id, urls=[url1, url2])

    # Transition url1 to processing, then completed
    temp_db.update_queue_item(job_id=job_id, url=url1, status="processing")
    summary = temp_db.get_queue_summary(job_id=job_id)
    assert summary["processing"] == 1
    assert summary["pending"] == 1

    temp_db.update_queue_item(job_id=job_id, url=url1, status="completed")
    summary = temp_db.get_queue_summary(job_id=job_id)
    assert summary["completed"] == 1
    assert summary["processing"] == 0

    # Transition url2 to failed with error message
    temp_db.update_queue_item(
        job_id=job_id,
        url=url2,
        status="failed",
        error_message="HTTP 500 Server Error",
    )
    summary = temp_db.get_queue_summary(job_id=job_id)
    assert summary["failed"] == 1
    assert summary["completed"] == 1
    assert summary["pending"] == 0


def test_get_resumable_job_and_crash_recovery(temp_db):
    """Verify finding an interrupted/failed job and retrieving only incomplete URLs."""
    job_id = "job-crash-100"
    urls = [
        "https://support.brilliantdirectories.com/article/done",
        "https://support.brilliantdirectories.com/article/pending1",
        "https://support.brilliantdirectories.com/article/pending2",
    ]

    temp_db.create_ingestion_job(job_id=job_id)
    temp_db.init_ingestion_queue(job_id=job_id, urls=urls)

    # First URL finishes before the simulated crash
    temp_db.update_queue_item(job_id=job_id, url=urls[0], status="completed")

    # Find resumable job
    resumable = temp_db.get_resumable_job()
    assert resumable is not None
    assert resumable["job_id"] == job_id

    # Pending queue should only return the 2 unfinished URLs
    pending = temp_db.get_pending_queue_urls(job_id=job_id)
    assert len(pending) == 2
    assert urls[0] not in pending
    assert urls[1] in pending
    assert urls[2] in pending
