"""Article schemas for ingestion, storage, and retrieval."""

from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class ImageMetadata(BaseModel):
    """Metadata for an image extracted from an article."""

    url: str
    alt_text: str | None = None
    nearest_heading: str | None = None
    description: str | None = None
    indexed_in_vector: bool = False


class ArticleBase(BaseModel):
    """Base fields for a help center article."""

    canonical_url: str
    title: str
    content: str
    headings: list[str] = Field(default_factory=list)
    images: list[ImageMetadata] = Field(default_factory=list)
    content_hash: str
    published_at: str | None = None
    modified_at: str | None = None


class ArticleCreate(ArticleBase):
    """Payload for creating or updating an article."""

    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class ArticleResponse(ArticleBase):
    """API response for a stored article."""

    id: str
    fetched_at: str
    status: str = "active"
    is_deleted: bool = False
    created_at: str
    updated_at: str


class ArticleListResponse(BaseModel):
    """Paginated or listed response of articles."""

    total: int
    articles: list[ArticleResponse]
