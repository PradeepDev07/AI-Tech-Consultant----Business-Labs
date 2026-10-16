"""HTML article parser for Brilliant Directories Solution Center."""

from datetime import datetime, timezone
import hashlib
import re
from typing import Any
import urllib.parse
from bs4 import BeautifulSoup, Tag
from app.core.exceptions import ParsingError
from app.schemas.articles import ImageMetadata


def compute_content_hash(text: str) -> str:
    """Generate SHA-256 hash of normalized text to detect actual content modifications."""
    normalized = " ".join(text.split()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ArticleParser:
    """Extracts structured article data, headings, and images from HTML."""

    # Selectors often used for article bodies in helpdesk software
    ARTICLE_BODY_SELECTORS = [
        "article",
        ".article-body",
        ".article-content",
        ".solution-article",
        ".content-body",
        "#article-body",
        "main",
        ".main-content",
    ]

    UNWANTED_TAGS = [
        "script",
        "style",
        "noscript",
        "header",
        "footer",
        "nav",
        "aside",
        "form",
        ".breadcrumbs",
        ".sidebar",
        ".navigation",
        ".feedback-container",
        ".comments",
    ]

    def parse_html(self, html: str, source_url: str) -> dict[str, Any]:
        """Parse raw HTML and extract title, content, headings, images, and content hash."""
        if not html or not html.strip():
            raise ParsingError("Empty HTML provided to parser.")

        soup = BeautifulSoup(html, "html.parser")

        # 1. Canonical URL
        canonical_tag = soup.find("link", rel=lambda val: val and "canonical" in val.lower())
        canonical_url = (
            canonical_tag["href"].strip()
            if (canonical_tag and canonical_tag.get("href"))
            else source_url
        )

        # 2. Extract Title
        title = self._extract_title(soup)

        # 3. Clean unwanted boilerplate elements
        for selector in self.UNWANTED_TAGS:
            for el in soup.select(selector):
                el.decompose()

        # 4. Locate main body
        body_elem = None
        for selector in self.ARTICLE_BODY_SELECTORS:
            found = soup.select_one(selector)
            if found and len(found.get_text(strip=True)) > 40:
                body_elem = found
                break

        if not body_elem:
            body_elem = soup.body or soup

        # 5. Extract Headings
        headings: list[str] = []
        for h in body_elem.find_all(re.compile(r"^h[1-6]$")):
            h_text = h.get_text(strip=True)
            if h_text and h_text not in headings:
                headings.append(h_text)

        # 6. Extract Images and associate with nearest preceding heading
        images: list[ImageMetadata] = self._extract_images(body_elem, canonical_url)

        # 7. Extract Main Text
        text_content = body_elem.get_text(separator="\n", strip=True)
        # Deduplicate consecutive blank lines
        cleaned_text = re.sub(r"\n{3,}", "\n\n", text_content).strip()

        if not cleaned_text:
            cleaned_text = title

        # 8. Content Hash
        content_hash = compute_content_hash(cleaned_text)

        # 9. Dates
        published_at, modified_at = self._extract_dates(soup)

        now_str = datetime.now(timezone.utc).isoformat()

        return {
            "canonical_url": canonical_url,
            "title": title,
            "content": cleaned_text,
            "headings": headings,
            "images": images,
            "content_hash": content_hash,
            "published_at": published_at,
            "modified_at": modified_at,
            "fetched_at": now_str,
            "status": "active",
            "is_deleted": False,
        }

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Find the most accurate article title."""
        # Check OpenGraph title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # Check H1
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        # Check <title>
        if soup.title and soup.title.get_text(strip=True):
            raw_title = soup.title.get_text(strip=True)
            # Remove site name suffixes like " | Brilliant Directories"
            return re.split(r"[\-|–]\s*(?:Brilliant Directories|Solution Center)", raw_title)[0].strip()

        return "Untitled Article"

    def _extract_images(
        self, body: Tag, base_url: str
    ) -> list[ImageMetadata]:
        """Extract images with alt text and identify nearest preceding heading context."""
        images: list[ImageMetadata] = []
        current_heading: str | None = None

        for element in body.descendants:
            if isinstance(element, Tag):
                if re.match(r"^h[1-6]$", element.name, re.IGNORECASE):
                    h_text = element.get_text(strip=True)
                    if h_text:
                        current_heading = h_text
                elif element.name == "img":
                    src = element.get("src") or element.get("data-src")
                    if not src:
                        continue

                    # Filter out tiny icons, spacers, tracking pixels
                    if any(s in src.lower() for s in ["icon", "pixel", "avatar", "logo", "badge"]):
                        continue

                    # Resolve relative URLs
                    abs_url = urllib.parse.urljoin(base_url, src.strip())
                    alt = element.get("alt", "").strip() or None

                    images.append(
                        ImageMetadata(
                            url=abs_url,
                            alt_text=alt,
                            nearest_heading=current_heading,
                            indexed_in_vector=False,
                        )
                    )
        return images

    def _extract_dates(
        self, soup: BeautifulSoup
    ) -> tuple[str | None, str | None]:
        """Attempt to extract publication and last modification dates."""
        pub_date: str | None = None
        mod_date: str | None = None

        meta_pub = soup.find(
            "meta", property=lambda v: v and v in ["article:published_time", "og:published_time"]
        )
        if meta_pub and meta_pub.get("content"):
            pub_date = meta_pub["content"].strip()

        meta_mod = soup.find(
            "meta", property=lambda v: v and v in ["article:modified_time", "og:updated_time"]
        )
        if meta_mod and meta_mod.get("content"):
            mod_date = meta_mod["content"].strip()

        return pub_date, mod_date
