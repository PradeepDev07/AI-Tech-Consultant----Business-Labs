"""Typed exceptions for Knowledge Brain application."""


class KnowledgeBrainError(Exception):
    """Base exception for all Knowledge Brain errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(KnowledgeBrainError):
    """Raised when environment configuration is missing or invalid."""
    pass


class IngestionError(KnowledgeBrainError):
    """Raised during sitemap retrieval or parsing."""
    pass


class CrawlerError(KnowledgeBrainError):
    """Raised during HTTP crawling of help center articles."""
    pass


class ParsingError(KnowledgeBrainError):
    """Raised when article HTML cannot be parsed."""
    pass


class StorageError(KnowledgeBrainError):
    """Raised during database operations."""
    pass


class ArticleNotFoundError(KnowledgeBrainError):
    """Raised when requested article does not exist."""
    pass


class VectorStoreError(KnowledgeBrainError):
    """Raised during vector indexing or searching."""
    pass


class RetrievalError(KnowledgeBrainError):
    """Raised during knowledge retrieval."""
    pass


class ModelProviderError(KnowledgeBrainError):
    """Raised when the language model provider fails or is unreachable."""
    pass


class VisionProviderError(KnowledgeBrainError):
    """Raised when image processing or vision model fails."""
    pass


class EscalationNotFoundError(KnowledgeBrainError):
    """Raised when an escalation record is not found."""
    pass


class AuthenticationError(KnowledgeBrainError):
    """Raised when API token verification fails."""
    pass
