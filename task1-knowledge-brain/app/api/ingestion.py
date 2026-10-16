"""Ingestion job trigger and observability API endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from app.core.exceptions import IngestionError
from app.dependencies import (
    get_cached_settings,
    get_database,
    get_vector_store_instance,
    verify_api_token,
)
from app.services.database import Database
from ingestion.scheduler import IngestionPipeline
from retrieval.vector_store import BaseVectorStore

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion_job(
    background_tasks: BackgroundTasks,
    force_refresh: bool = Query(default=False),
    resume: bool = Query(default=False, description="Resume interrupted ingestion job from persistent queue"),
    db: Database = Depends(get_database),
    vector_store: BaseVectorStore = Depends(get_vector_store_instance),
    settings=Depends(get_cached_settings),
    _auth: None = Depends(verify_api_token),
):
    """Trigger an incremental ingestion and change-detection job with optional crash resumption."""
    pipeline = IngestionPipeline(
        db=db,
        vector_store=vector_store,
        sitemap_url=settings.sitemap_url,
        concurrency=settings.crawler_concurrency,
        request_delay_seconds=settings.crawler_request_delay_seconds,
    )

    if pipeline._is_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An ingestion run is already in progress.",
        )

    # Launch ingestion job in background
    background_tasks.add_task(pipeline.run_incremental_job, force_refresh, resume)

    return {
        "status": "accepted",
        "message": "Ingestion job initiated in the background.",
        "force_refresh": force_refresh,
        "resume": resume,
    }


@router.get("/status")
async def get_ingestion_status(
    db: Database = Depends(get_database),
):
    """Retrieve the latest ingestion job status and metrics."""
    job = db.get_latest_ingestion_job()
    if not job:
        return {
            "status": "idle",
            "message": "No ingestion jobs have been recorded yet.",
        }
    job["queue_summary"] = db.get_queue_summary(job["job_id"])
    return job
