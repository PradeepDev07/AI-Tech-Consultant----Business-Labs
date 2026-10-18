"""Model provider configuration and runtime switching endpoints for Task 3."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import get_provider_manager_instance
from app.providers.model_provider import ProviderManager

router = APIRouter(prefix="/api/v1/provider", tags=["provider"])


class ProviderSelectRequest(BaseModel):
    provider: str = Field(..., description="Provider type: 'mock', 'ollama', or 'claude'")
    model: str | None = Field(None, description="Model identifier")
    api_key: str | None = Field(None, description="Optional API key for Claude")
    base_url: str | None = Field(None, description="Optional base URL for Ollama")


class ProviderTestRequest(BaseModel):
    provider: str = Field(..., description="Provider type: 'mock', 'ollama', or 'claude'")
    model: str | None = Field(None, description="Model identifier")
    api_key: str | None = Field(None, description="Optional API key for Claude")
    base_url: str | None = Field(None, description="Optional base URL for Ollama")


@router.get("", summary="Get current provider status")
@router.get("/status", summary="Get current provider status (alias)")
async def get_provider_status(
    manager: ProviderManager = Depends(get_provider_manager_instance),
) -> dict[str, Any]:
    """Return active provider and configuration options without exposing secrets."""
    return manager.get_status()


@router.post("/select", summary="Select active model provider")
async def select_provider(
    request: ProviderSelectRequest,
    manager: ProviderManager = Depends(get_provider_manager_instance),
) -> dict[str, Any]:
    """Switch active provider at runtime."""
    try:
        return manager.set_active_provider(
            provider_type=request.provider,
            model=request.model,
            api_key=request.api_key,
            base_url=request.base_url,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.post("/test", summary="Test provider connectivity")
async def test_provider(
    request: ProviderTestRequest,
    manager: ProviderManager = Depends(get_provider_manager_instance),
) -> dict[str, Any]:
    """Check connectivity to candidate provider without making it active."""
    return manager.test_provider(
        provider_type=request.provider,
        model=request.model,
        api_key=request.api_key,
        base_url=request.base_url,
    )
