"""Unit tests for change detection logic."""

import tempfile
from app.services.database import Database
from ingestion.change_detector import ChangeDetector
from ingestion.sitemap import DiscoveredUrl


def test_change_detector_new_unchanged_and_removed():
    """Verify change detector categorizes new, unchanged, and removed URLs."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db = Database(tmp.name)

        # Pre-populate database with 2 articles
        db.upsert_article({
            "canonical_url": "https://support.brilliantdirectories.com/article/1",
            "title": "Article 1",
            "content": "Content 1",
            "content_hash": "hash1",
            "modified_at": "2026-03-01T00:00:00Z",
        })
        db.upsert_article({
            "canonical_url": "https://support.brilliantdirectories.com/article/2",
            "title": "Article 2",
            "content": "Content 2",
            "content_hash": "hash2",
            "modified_at": "2026-03-01T00:00:00Z",
        })

        # New sitemap contains:
        # Article 1 (same lastmod -> unchanged)
        # Article 3 (not in DB -> new)
        # (Article 2 is absent from sitemap -> removed)
        discovered = [
            DiscoveredUrl(
                url="https://support.brilliantdirectories.com/article/1",
                lastmod="2026-03-01T00:00:00Z",
            ),
            DiscoveredUrl(
                url="https://support.brilliantdirectories.com/article/3",
                lastmod="2026-03-05T00:00:00Z",
            ),
        ]

        detector = ChangeDetector(db=db)
        plan = detector.analyze_sitemap(discovered)

        assert plan.new_urls == ["https://support.brilliantdirectories.com/article/3"]
        assert plan.unchanged_urls == ["https://support.brilliantdirectories.com/article/1"]
        assert plan.removed_urls == ["https://support.brilliantdirectories.com/article/2"]
