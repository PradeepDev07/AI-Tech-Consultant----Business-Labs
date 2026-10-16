"""Unit tests for sitemap discovery, XML parsing, and URL normalization."""

from pathlib import Path
from ingestion.sitemap import (
    SitemapParser,
    is_url_in_allowed_domain,
    normalize_url,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_url_normalization():
    """Verify fragment removal, query parameter filtering, and trailing slash handling."""
    raw = "HTTPS://Support.BrilliantDirectories.COM/support/articles/123/?utm_source=email&ref=newsletter#section-2"
    normalized = normalize_url(raw)
    assert normalized == "https://support.brilliantdirectories.com/support/articles/123"

    # Preserves legitimate non-tracking query parameters
    raw_query = "https://support.brilliantdirectories.com/search?q=billing&page=2"
    assert normalize_url(raw_query) == "https://support.brilliantdirectories.com/search?page=2&q=billing"


def test_domain_validation():
    """Verify only allowed domain URLs are accepted."""
    allowed = "support.brilliantdirectories.com"
    assert is_url_in_allowed_domain("https://support.brilliantdirectories.com/article/1", allowed)
    assert not is_url_in_allowed_domain("https://attacker.com/article/1", allowed)
    assert not is_url_in_allowed_domain("https://brilliantdirectories.com/article/1", allowed)


def test_parse_sitemap_xml():
    """Verify parsing of urlset, exclusion of out-of-domain URLs, and deduplication."""
    xml_content = (FIXTURES_DIR / "sample_sitemap.xml").read_text()
    parser = SitemapParser(allowed_host="support.brilliantdirectories.com")

    urls, sub_sitemaps = parser.parse_xml_content(xml_content)

    assert len(sub_sitemaps) == 0
    # The fixture contains 4 entries: 1 with utm/fragment, 1 normal, 1 malicious external, 1 duplicate
    # Only 2 unique valid articles should remain
    assert len(urls) == 2
    urls_list = [u.url for u in urls]
    assert "https://support.brilliantdirectories.com/support/solutions/articles/12000000001-how-to-set-up-payment-gateways" in urls_list
    assert "https://support.brilliantdirectories.com/support/solutions/articles/12000000002-managing-member-categories" in urls_list
    assert "https://malicious-external-site.com/phishing" not in urls_list


def test_parse_sitemap_index():
    """Verify parsing of sitemap index files."""
    xml_content = (FIXTURES_DIR / "sample_sitemap_index.xml").read_text()
    parser = SitemapParser(allowed_host="support.brilliantdirectories.com")

    urls, sub_sitemaps = parser.parse_xml_content(xml_content)
    assert len(urls) == 0
    # evil-site.com sitemap should be rejected by domain check
    assert len(sub_sitemaps) == 1
    assert sub_sitemaps[0] == "https://support.brilliantdirectories.com/support/sitemap-articles.xml"
