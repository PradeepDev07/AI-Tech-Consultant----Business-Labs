"""Article service orchestrating persistence and retrieval updates."""

from typing import Any
from app.core.exceptions import ArticleNotFoundError
from app.schemas.articles import ArticleListResponse, ArticleResponse
from app.services.database import Database


class ArticleService:
    """Service handling article management and lifecycle."""

    def __init__(self, db: Database, vector_store=None):
        self.db = db
        self.vector_store = vector_store

    def get_article(self, article_id: str) -> ArticleResponse:
        """Retrieve an article by ID or raise ArticleNotFoundError."""
        article = self.db.get_article(article_id)
        if not article:
            raise ArticleNotFoundError(f"Article with ID '{article_id}' not found.")
        return ArticleResponse(**article)

    def list_articles(
        self, limit: int = 50, offset: int = 0, include_deleted: bool = False
    ) -> ArticleListResponse:
        """List articles with pagination."""
        articles, total = self.db.list_articles(
            limit=limit, offset=offset, include_deleted=include_deleted
        )
        return ArticleListResponse(
            total=total,
            articles=[ArticleResponse(**a) for a in articles],
        )

    def upsert_article(self, article_data: dict[str, Any]) -> ArticleResponse:
        """Persist or update an article."""
        saved = self.db.upsert_article(article_data)
        return ArticleResponse(**saved)

    def delete_article(self, article_id: str) -> bool:
        """Mark an article as removed in DB and remove its chunks from the vector store."""
        article = self.db.get_article(article_id)
        if not article:
            raise ArticleNotFoundError(f"Article with ID '{article_id}' not found.")

        success = self.db.mark_article_deleted(article_id)
        if success and self.vector_store is not None:
            self.vector_store.delete_article_chunks(article_id)
        return success
