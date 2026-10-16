"""Articles API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.exceptions import ArticleNotFoundError
from app.dependencies import get_article_service
from app.schemas.articles import ArticleListResponse, ArticleResponse
from app.services.article_service import ArticleService

router = APIRouter(prefix="/api/v1/articles", tags=["articles"])


@router.get("", response_model=ArticleListResponse)
async def list_articles(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_deleted: bool = Query(default=False),
    service: ArticleService = Depends(get_article_service),
):
    """Retrieve paginated list of ingested help center articles."""
    return service.list_articles(
        limit=limit, offset=offset, include_deleted=include_deleted
    )


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: str,
    service: ArticleService = Depends(get_article_service),
):
    """Retrieve a single article by its unique ID."""
    try:
        return service.get_article(article_id)
    except ArticleNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
