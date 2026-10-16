"""Health check API endpoint."""

from fastapi import APIRouter, Depends
from app.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint exposing system readiness and configured providers."""
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "model_provider": settings.model_provider,
        "chat_model": settings.chat_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "vision_provider": settings.vision_provider,
        "database": "sqlite",
    }
