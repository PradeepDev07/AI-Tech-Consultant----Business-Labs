"""Health and diagnostic endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from app.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(settings: Settings = Depends(get_settings)):
    """System health check and runtime configuration status."""
    return {
        "status": "ok",
        "service": "task3-meeting-to-scope",
        "environment": settings.ENVIRONMENT,
        "model_provider": settings.MODEL_PROVIDER,
        "model_name": settings.MODEL_NAME,
        "task1_api_base_url": settings.TASK1_API_BASE_URL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
