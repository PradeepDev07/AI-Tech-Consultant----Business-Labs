"""Context-aware chunking preserving article hierarchy, title, and section headings."""

from dataclasses import dataclass
import re
from typing import Any


@dataclass
class ArticleChunk:
    """A semantic chunk derived from an article with provenance metadata."""

    chunk_id: str
    article_id: str
    article_title: str
    source_url: str
    heading: str | None
    chunk_index: int
    content_hash: str
    text: str
    metadata: dict[str, Any]


class ArticleChunker:
    """Splits article text into overlapping chunks while preserving heading and document context."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_article(self, article: dict[str, Any]) -> list[ArticleChunk]:
        """Convert an article dictionary into a sequence of contextualized chunks."""
        article_id = article["id"]
        title = article["title"]
        canonical_url = article["canonical_url"]
        content = article.get("content", "")
        content_hash = article.get("content_hash", "")
        headings = article.get("headings", [])

        if not content.strip():
            return []

        # Split content into section blocks based on headings or paragraphs
        sections = self._split_into_sections(content, headings)
        chunks: list[ArticleChunk] = []
        chunk_idx = 0

        for section_heading, section_text in sections:
            section_chunks = self._sliding_window_chunks(section_text)
            for text_piece in section_chunks:
                # Prepend document and heading context
                context_prefix = f"Article: {title}\n"
                if section_heading:
                    context_prefix += f"Section: {section_heading}\n"
                context_prefix += "\n"

                full_chunk_text = f"{context_prefix}{text_piece}".strip()

                chunk_id = f"{article_id}-c{chunk_idx}"
                metadata = {
                    "chunk_id": chunk_id,
                    "article_id": article_id,
                    "title": title,
                    "source_url": canonical_url,
                    "heading": section_heading,
                    "chunk_index": chunk_idx,
                    "content_hash": content_hash,
                }

                chunks.append(
                    ArticleChunk(
                        chunk_id=chunk_id,
                        article_id=article_id,
                        article_title=title,
                        source_url=canonical_url,
                        heading=section_heading,
                        chunk_index=chunk_idx,
                        content_hash=content_hash,
                        text=full_chunk_text,
                        metadata=metadata,
                    )
                )
                chunk_idx += 1

        return chunks

    def _split_into_sections(
        self, content: str, headings: list[str]
    ) -> list[tuple[str | None, str]]:
        """Split text into sections keyed by nearest heading."""
        if not headings:
            return [(None, content)]

        # Construct regex pattern matching any of the known headings on its own line
        escaped_headings = [re.escape(h) for h in headings if h.strip()]
        if not escaped_headings:
            return [(None, content)]

        pattern = r"(?:^|\n)(?=(" + "|".join(escaped_headings) + r")(?:\n|$))"
        parts = re.split(pattern, content)

        sections: list[tuple[str | None, str]] = []
        current_heading: str | None = None

        for part in parts:
            part_str = part.strip()
            if not part_str:
                continue
            if part_str in headings:
                current_heading = part_str
            else:
                sections.append((current_heading, part_str))

        if not sections:
            sections = [(None, content)]
        return sections

    def _sliding_window_chunks(self, text: str) -> list[str]:
        """Split a string into overlapping window segments without splitting words."""
        if len(text) <= self.chunk_size:
            return [text.strip()]

        paragraphs = text.split("\n\n")
        chunks: list[str] = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if not current_chunk:
                current_chunk = para
            elif len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk += "\n\n" + para
            else:
                chunks.append(current_chunk)
                # Apply overlap by keeping tail of current_chunk
                if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                    tail = current_chunk[-self.chunk_overlap :]
                    # Try to break on whitespace in tail
                    split_idx = tail.find(" ")
                    if split_idx != -1:
                        tail = tail[split_idx + 1 :]
                    current_chunk = tail + "\n\n" + para
                else:
                    current_chunk = para

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks
