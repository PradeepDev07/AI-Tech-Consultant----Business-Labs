"""Unit tests for multimodal image extraction and vision pipeline."""

from multimodal.image_extractor import ImageExtractor
from multimodal.image_processor import (
    ImageProcessingPipeline,
    MockVisionProvider,
    NoneVisionProvider,
)


def test_image_extractor():
    """Verify image extractor captures alt text, nearest headings, and filters icons."""
    html = """
    <html>
    <body>
      <h1>Payment Settings</h1>
      <p>Configure Stripe below.</p>
      <img src="/icons/favicon.ico" alt="icon" />
      <h2>Stripe Webhook Configuration</h2>
      <img src="https://example.com/webhook-screen.png" alt="Stripe Webhooks Endpoint" />
    </body>
    </html>
    """
    extractor = ImageExtractor()
    images = extractor.extract_images_from_html(html, "https://support.brilliantdirectories.com")

    # Favicon should be excluded
    assert len(images) == 1
    assert images[0].url == "https://example.com/webhook-screen.png"
    assert images[0].alt_text == "Stripe Webhooks Endpoint"
    assert images[0].nearest_heading == "Stripe Webhook Configuration"


def test_none_vision_provider():
    """Verify default provider honestly reports image understanding as unavailable."""
    provider = NoneVisionProvider()
    assert provider.is_available is False
    assert provider.provider_name == "none"
    assert provider.describe_image("https://example.com/image.png") is None


def test_mock_vision_provider_and_pipeline():
    """Verify vision pipeline caches descriptions and produces indexed image chunks."""
    vision_provider = MockVisionProvider()
    pipeline = ImageProcessingPipeline(vision_provider=vision_provider)

    article = {
        "id": "art-webhooks",
        "title": "Webhook Setup",
        "canonical_url": "https://support.brilliantdirectories.com/webhooks",
        "images": [
            {
                "url": "https://example.com/screen1.png",
                "alt_text": "Webhook secret key entry",
                "nearest_heading": "Configuration",
            }
        ],
    }

    chunks = pipeline.process_article_images(article)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["chunk_id"] == "art-webhooks-img-0"
    assert "Webhook secret key entry" in chunk["text"]
    assert chunk["metadata"]["source_type"] == "article_screenshot"

    # Processing again should hit cache
    assert "https://example.com/screen1.png" in pipeline._description_cache


def test_ocr_vision_provider_custom_engine(tmp_path):
    """Verify OCR vision provider with custom OCR engine extracts text."""
    from multimodal.image_processor import OCRVisionProvider, get_cached_image_path

    # Pre-populate disk cache with dummy image bytes
    image_url = "https://example.com/sample-screenshot.png"
    cached_file = get_cached_image_path(image_url, tmp_path)
    cached_file.parent.mkdir(parents=True, exist_ok=True)
    cached_file.write_bytes(b"FAKE_PNG_BYTES")

    def mock_ocr(raw_bytes: bytes) -> str:
        return "Webhook Endpoint: /api/v1/stripe-notify"

    ocr_provider = OCRVisionProvider(cache_dir=tmp_path, ocr_engine=mock_ocr)
    assert ocr_provider.is_available is True
    assert ocr_provider.provider_name == "ocr:custom"

    desc = ocr_provider.describe_image(
        image_url=image_url,
        alt_text="Settings dialog",
        context_heading="Webhooks",
    )
    assert desc is not None
    assert "Webhook Endpoint: /api/v1/stripe-notify" in desc
    assert "section 'Webhooks'" in desc


def test_ocr_vision_provider_offline_fallback():
    """Verify OCR provider returns fallback alt text when image is offline."""
    from multimodal.image_processor import OCRVisionProvider

    ocr_provider = OCRVisionProvider(cache_dir=None)
    desc = ocr_provider.describe_image(
        image_url="http://invalid.local/missing.png",
        alt_text="Stripe Account Toggle",
        context_heading="Billing",
    )
    assert desc is not None
    assert "Stripe Account Toggle" in desc
    assert "section 'Billing'" in desc


def test_image_pipeline_disk_cache_persistence(tmp_path):
    """Verify ImageProcessingPipeline persists and reloads description cache across instances."""
    from multimodal.image_processor import MockVisionProvider, ImageProcessingPipeline

    provider = MockVisionProvider()
    pipeline1 = ImageProcessingPipeline(vision_provider=provider, cache_dir=tmp_path)

    article = {
        "id": "art-101",
        "title": "Directory Pricing",
        "canonical_url": "https://example.com/pricing",
        "images": [
            {
                "url": "https://example.com/pricing-table.png",
                "alt_text": "Monthly and Yearly Plans",
                "nearest_heading": "Membership Plans",
            }
        ],
    }

    chunks1 = pipeline1.process_article_images(article)
    assert len(chunks1) == 1
    assert (tmp_path / "descriptions.json").exists()

    # Create new pipeline instance pointing to same cache directory
    pipeline2 = ImageProcessingPipeline(vision_provider=provider, cache_dir=tmp_path)
    assert "https://example.com/pricing-table.png" in pipeline2._description_cache
    chunks2 = pipeline2.process_article_images(article)
    assert len(chunks2) == 1
    assert chunks2[0]["text"] == chunks1[0]["text"]


def test_create_vision_provider_factory(tmp_path):
    """Verify create_vision_provider returns expected provider types."""
    from multimodal.image_processor import (
        create_vision_provider,
        MockVisionProvider,
        NoneVisionProvider,
        OCRVisionProvider,
    )
    from types import SimpleNamespace

    mock_cfg = SimpleNamespace(
        vision_provider="mock",
        vision_model="mock-v2",
        resolve_image_cache_path=lambda: tmp_path,
    )
    prov_mock = create_vision_provider(mock_cfg)
    assert isinstance(prov_mock, MockVisionProvider)
    assert prov_mock.provider_name == "mock:mock-v2"

    none_cfg = SimpleNamespace(
        vision_provider="none",
        resolve_image_cache_path=lambda: tmp_path,
    )
    prov_none = create_vision_provider(none_cfg)
    assert isinstance(prov_none, NoneVisionProvider)

    ocr_cfg = SimpleNamespace(
        vision_provider="ocr",
        resolve_image_cache_path=lambda: tmp_path,
    )
    prov_ocr = create_vision_provider(ocr_cfg)
    assert isinstance(prov_ocr, OCRVisionProvider)

