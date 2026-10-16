"""Unit tests for HTML article parser, heading extraction, and image association."""

from pathlib import Path
from ingestion.parser import ArticleParser, compute_content_hash

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_article_parser_extraction():
    """Verify title, body, headings, images, and content hash from realistic HTML."""
    html_content = (FIXTURES_DIR / "sample_article.html").read_text()
    source_url = "https://support.brilliantdirectories.com/support/solutions/articles/12000000001-how-to-set-up-payment-gateways"

    parser = ArticleParser()
    result = parser.parse_html(html_content, source_url)

    assert result["title"] == "How to Set Up Payment Gateways"
    assert result["canonical_url"] == source_url
    assert "Brilliant Directories supports multiple payment gateways" in result["content"]

    # Boilerplate navigation and sidebar should have been removed
    assert "Related Articles" not in result["content"]
    assert "Home" not in result["content"]

    # Check headings
    assert "Supported Payment Gateways" in result["headings"]
    assert "Webhooks Configuration" in result["headings"]
    assert "Troubleshooting Failed Payments" in result["headings"]

    # Check images & association with nearest heading
    assert len(result["images"]) == 1
    image = result["images"][0]
    assert image.url == "https://support.brilliantdirectories.com/assets/images/stripe-setup.png"
    assert image.alt_text == "Stripe Setup Configuration Screen"
    assert image.nearest_heading == "Supported Payment Gateways"

    # Check content hash
    assert result["content_hash"] == compute_content_hash(result["content"])


def test_content_hash_consistency():
    """Verify hash remains identical for whitespace variations and changes when text changes."""
    text1 = "This is a test article body.\n\nWith multiple lines."
    text2 = "This is a test article body. With multiple lines."
    text3 = "This is an altered article body."

    assert compute_content_hash(text1) == compute_content_hash(text2)
    assert compute_content_hash(text1) != compute_content_hash(text3)
