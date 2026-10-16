"""Change detector identifying added, updated, unchanged, and removed articles."""

from dataclasses import dataclass, field
from typing import Sequence
from app.services.database import Database
from ingestion.sitemap import DiscoveredUrl


@dataclass
class ChangePlan:
    """Summary plan of detected differences between sitemap and stored database state."""

    new_urls: list[str] = field(default_factory=list)
    existing_urls_to_check: list[str] = field(default_factory=list)
    unchanged_urls: list[str] = field(default_factory=list)
    removed_urls: list[str] = field(default_factory=list)


class ChangeDetector:
    """Compares incoming sitemap entries with stored database state."""

    def __init__(self, db: Database):
        self.db = db

    def analyze_sitemap(self, discovered_urls: Sequence[DiscoveredUrl]) -> ChangePlan:
        """Compare discovered sitemap URLs with database records."""
        # 1. Fetch all active articles currently in database
        stored_articles, _ = self.db.list_articles(limit=100000, include_deleted=False)
        stored_url_map = {a["canonical_url"]: a for a in stored_articles}

        discovered_url_map = {d.url: d for d in discovered_urls}

        new_urls: list[str] = []
        existing_to_check: list[str] = []
        unchanged_urls: list[str] = []

        for url, disc in discovered_url_map.items():
            if url not in stored_url_map:
                new_urls.append(url)
            else:
                stored = stored_url_map[url]
                # If sitemap has lastmod and it matches stored modified_at, we can consider unchanged
                if disc.lastmod and stored.get("modified_at") == disc.lastmod:
                    unchanged_urls.append(url)
                else:
                    existing_to_check.append(url)

        # 2. Identify removed URLs (in stored database as active, but absent from sitemap)
        removed_urls: list[str] = [
            url for url in stored_url_map if url not in discovered_url_map
        ]

        return ChangePlan(
            new_urls=new_urls,
            existing_urls_to_check=existing_to_check,
            unchanged_urls=unchanged_urls,
            removed_urls=removed_urls,
        )

    def is_content_changed(self, stored_content_hash: str, new_content_hash: str) -> bool:
        """Determine if article body actually changed via content hash comparison."""
        return stored_content_hash != new_content_hash
