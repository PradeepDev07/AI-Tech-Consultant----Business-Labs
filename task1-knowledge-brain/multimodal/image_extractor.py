"""Image extractor extracting image metadata and association with article hierarchy."""

import re
import urllib.parse
from bs4 import BeautifulSoup, Tag
from app.schemas.articles import ImageMetadata


class ImageExtractor:
    """Extracts screenshot images and contextual headings from article HTML."""

    IGNORABLE_PATTERNS = [
        "avatar",
        "icon",
        "favicon",
        "logo",
        "badge",
        "pixel",
        "tracker",
        "button",
        "spinner",
        "arrow",
    ]

    def extract_images_from_html(
        self, html: str, base_url: str
    ) -> list[ImageMetadata]:
        """Extract valid image URLs with their alt text and nearest preceding heading."""
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        body = (
            soup.find("article")
            or soup.find(class_=re.compile(r"article|content|body", re.I))
            or soup.body
            or soup
        )

        extracted: list[ImageMetadata] = []
        seen_urls: set[str] = set()
        current_heading: str | None = None

        for elem in body.descendants:
            if isinstance(elem, Tag):
                if re.match(r"^h[1-6]$", elem.name, re.I):
                    h_text = elem.get_text(strip=True)
                    if h_text:
                        current_heading = h_text
                elif elem.name == "img":
                    src = elem.get("src") or elem.get("data-src")
                    if not src:
                        continue

                    # Filter out UI icons, avatars, and decorative graphics
                    src_lower = src.lower()
                    if any(pat in src_lower for pat in self.IGNORABLE_PATTERNS):
                        continue

                    # Resolve absolute URL
                    abs_url = urllib.parse.urljoin(base_url, src.strip())
                    if abs_url in seen_urls:
                        continue
                    seen_urls.add(abs_url)

                    alt = elem.get("alt", "").strip() or None

                    extracted.append(
                        ImageMetadata(
                            url=abs_url,
                            alt_text=alt,
                            nearest_heading=current_heading,
                            indexed_in_vector=False,
                        )
                    )
        return extracted
