"""Image processing provider interfaces, caching, and screenshot indexing."""

from abc import ABC, abstractmethod
import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Callable
import httpx
from app.core.exceptions import VisionProviderError
from app.core.logging import logger
from app.schemas.articles import ImageMetadata


def get_cached_image_path(image_url: str, cache_dir: Path) -> Path:
    """Compute local filesystem destination path for a given image URL."""
    url_hash = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
    parsed = image_url.split("?")[0].split("/")[-1]
    ext = ".png"
    if "." in parsed:
        candidate_ext = f".{parsed.split('.')[-1].lower()}"
        if candidate_ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}:
            ext = candidate_ext
    return cache_dir / f"{url_hash[:16]}{ext}"


def fetch_or_cache_image(
    image_url: str,
    cache_dir: Path | None = None,
    timeout_seconds: float = 15.0,
) -> bytes | None:
    """Fetch image bytes from cache if present, otherwise download and persist to disk cache."""
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_file = get_cached_image_path(image_url, cache_dir)
        if cached_file.exists() and cached_file.stat().st_size > 0:
            try:
                return cached_file.read_bytes()
            except Exception as exc:
                logger.warning(f"Failed to read cached image {cached_file}: {exc}")

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = client.get(image_url)
            if resp.status_code == 200:
                data = resp.content
                if cache_dir:
                    try:
                        cached_file = get_cached_image_path(image_url, cache_dir)
                        cached_file.write_bytes(data)
                    except Exception as write_exc:
                        logger.warning(f"Failed to write image to disk cache {image_url}: {write_exc}")
                return data
            logger.warning(f"Could not fetch image at {image_url} (HTTP {resp.status_code})")
            return None
    except Exception as exc:
        logger.warning(f"Failed to download image {image_url}: {exc}")
        return None


class BaseVisionProvider(ABC):
    """Abstract interface for image understanding and visual captioning."""

    @abstractmethod
    def describe_image(
        self, image_url: str, alt_text: str | None = None, context_heading: str | None = None, **kwargs: Any
    ) -> str | None:
        """Generate structured visual description of an image."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Indicate whether the vision provider is configured and operational."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identify vision provider name and model."""
        pass


class NoneVisionProvider(BaseVisionProvider):
    """Default provider when no vision model is configured. Honestly reports image understanding as unavailable."""

    @property
    def is_available(self) -> bool:
        return False

    @property
    def provider_name(self) -> str:
        return "none"

    def describe_image(
        self, image_url: str, alt_text: str | None = None, context_heading: str | None = None, **kwargs: Any
    ) -> str | None:
        # Honestly report image understanding as unavailable
        return None


class MockVisionProvider(BaseVisionProvider):
    """Deterministic vision double for testing and evaluation."""

    def __init__(self, model_name: str = "mock-vision-v1", cache_dir: Path | str | None = None):
        self.model_name = model_name
        self.cache_dir = Path(cache_dir) if cache_dir else None

    @property
    def is_available(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return f"mock:{self.model_name}"

    def describe_image(
        self, image_url: str, alt_text: str | None = None, context_heading: str | None = None, **kwargs: Any
    ) -> str | None:
        """Synthesize descriptive caption based on alt text and section context."""
        context = f" in section '{context_heading}'" if context_heading else ""
        if alt_text:
            return f"[Visual Screenshot Analysis]: Interface screenshot showing {alt_text}{context}."
        filename = image_url.split("/")[-1].split("?")[0]
        return f"[Visual Screenshot Analysis]: Interface screenshot from {filename}{context}."


class OCRVisionProvider(BaseVisionProvider):
    """Local offline OCR fallback for extracting text from documentation screenshots."""

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        ocr_engine: Callable[[bytes], str] | None = None,
        timeout_seconds: float = 15.0,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.ocr_engine = ocr_engine
        self.timeout_seconds = timeout_seconds

    @property
    def is_available(self) -> bool:
        if self.ocr_engine is not None:
            return True
        try:
            import pytesseract
            return True
        except ImportError:
            pass
        try:
            import PIL
            return True
        except ImportError:
            return False

    @property
    def provider_name(self) -> str:
        if self.ocr_engine is not None:
            return "ocr:custom"
        try:
            import pytesseract
            return "ocr:pytesseract"
        except ImportError:
            return "ocr:pil-fallback"

    def describe_image(
        self, image_url: str, alt_text: str | None = None, context_heading: str | None = None, **kwargs: Any
    ) -> str | None:
        """Extract text or structural metadata from screenshot using offline OCR / image analysis."""
        img_bytes = fetch_or_cache_image(image_url, self.cache_dir, timeout_seconds=self.timeout_seconds)
        if not img_bytes:
            if alt_text:
                context = f" in section '{context_heading}'" if context_heading else ""
                return f"[Visual OCR Analysis]: Image offline fallback; alt text: '{alt_text}'{context}"
            return None

        # 1. Custom injected engine (ideal for deterministic unit tests)
        if self.ocr_engine is not None:
            try:
                extracted = self.ocr_engine(img_bytes)
                if extracted and extracted.strip():
                    context = f" in section '{context_heading}'" if context_heading else ""
                    return f"[Visual OCR Analysis]: Screenshot contains text: '{extracted.strip()}'{context}"
            except Exception as exc:
                logger.warning(f"Custom OCR engine failure: {exc}")

        # 2. pytesseract if available
        try:
            import io
            from PIL import Image
            import pytesseract

            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img).strip()
            if text:
                context = f" in section '{context_heading}'" if context_heading else ""
                return f"[Visual OCR Analysis]: Screenshot contains text: '{text}'{context}"
        except ImportError:
            pass
        except Exception as exc:
            logger.warning(f"pytesseract extraction error on {image_url}: {exc}")

        # 3. PIL metadata fallback
        try:
            import io
            from PIL import Image

            img = Image.open(io.BytesIO(img_bytes))
            width, height = img.size
            fmt = img.format or "IMAGE"
            context = f" in section '{context_heading}'" if context_heading else ""
            alt_info = f" with description '{alt_text}'" if alt_text else ""
            return f"[Visual Image Analysis]: {fmt.upper()} screenshot ({width}x{height}px){alt_info}{context}."
        except Exception as exc:
            logger.warning(f"PIL fallback inspection failed on {image_url}: {exc}")

        if alt_text:
            context = f" in section '{context_heading}'" if context_heading else ""
            return f"[Visual Image Analysis]: Screenshot showing {alt_text}{context}."

        return None


class OllamaVisionProvider(BaseVisionProvider):
    """Client for Ollama vision models (e.g. llava, moondream)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llava:latest",
        timeout_seconds: float = 30.0,
        cache_dir: Path | str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.cache_dir = Path(cache_dir) if cache_dir else None

    @property
    def is_available(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return f"ollama_vision:{self.model}"

    def describe_image(
        self, image_url: str, alt_text: str | None = None, context_heading: str | None = None, **kwargs: Any
    ) -> str | None:
        """Attempt to fetch/cached image bytes and invoke Ollama vision model."""
        img_bytes = fetch_or_cache_image(image_url, self.cache_dir, timeout_seconds=self.timeout_seconds)
        if not img_bytes:
            return None

        try:
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            prompt = (
                "Describe this software documentation screenshot in detail. "
                "List all visible settings, buttons, and form fields accurately."
            )
            if context_heading:
                prompt += f" Context section: {context_heading}."

            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [img_b64],
                "stream": False,
            }
            with httpx.Client(timeout=self.timeout_seconds) as client:
                api_resp = client.post(f"{self.base_url}/api/generate", json=payload)
                if api_resp.status_code == 200:
                    data = api_resp.json()
                    return data.get("response", "").strip() or None
            return None
        except Exception as exc:
            logger.warning(f"Failed to process image {image_url} with vision model: {exc}")
            return None


def create_vision_provider(settings: Any = None) -> BaseVisionProvider:
    """Instantiate configured vision provider based on application settings."""
    if settings is None:
        try:
            from app.config import get_settings
            settings = get_settings()
        except Exception:
            return NoneVisionProvider()

    provider_type = getattr(settings, "vision_provider", "none").lower()
    image_cache = None
    if hasattr(settings, "resolve_image_cache_path"):
        try:
            image_cache = settings.resolve_image_cache_path()
        except Exception:
            image_cache = None

    if provider_type == "mock":
        return MockVisionProvider(
            model_name=getattr(settings, "vision_model", "mock-vision-v1"),
            cache_dir=image_cache,
        )
    elif provider_type == "ollama":
        return OllamaVisionProvider(
            base_url=getattr(settings, "ollama_base_url", "http://localhost:11434"),
            model=getattr(settings, "vision_model", "llava:latest"),
            cache_dir=image_cache,
        )
    elif provider_type in ("ocr", "tesseract"):
        return OCRVisionProvider(cache_dir=image_cache)
    elif provider_type == "none":
        return NoneVisionProvider()
    else:
        logger.warning(f"Unknown vision provider '{provider_type}', falling back to NoneVisionProvider.")
        return NoneVisionProvider()


class ImageProcessingPipeline:
    """Coordinates image extraction, vision description, caching, and vector indexing chunks."""

    def __init__(
        self,
        vision_provider: BaseVisionProvider,
        cache_dir: Path | str | None = None,
    ):
        self.vision_provider = vision_provider
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._description_cache: dict[str, str] = {}
        self._load_description_cache()

    def _get_cache_manifest_path(self) -> Path | None:
        if self.cache_dir:
            return self.cache_dir / "descriptions.json"
        return None

    def _load_description_cache(self) -> None:
        manifest = self._get_cache_manifest_path()
        if manifest and manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._description_cache.update(data)
            except Exception as exc:
                logger.warning(f"Failed to load image descriptions cache from {manifest}: {exc}")

    def _save_description_cache(self) -> None:
        manifest = self._get_cache_manifest_path()
        if manifest:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                manifest.write_text(json.dumps(self._description_cache, indent=2), encoding="utf-8")
            except Exception as exc:
                logger.warning(f"Failed to save image descriptions cache to {manifest}: {exc}")

    def process_article_images(
        self, article: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Process images for an article and generate searchable visual chunks."""
        if not self.vision_provider.is_available:
            return []

        images: list[ImageMetadata] = article.get("images", [])
        if not images:
            return []

        article_id = article["id"]
        article_title = article["title"]
        canonical_url = article["canonical_url"]

        image_chunks: list[dict[str, Any]] = []

        for idx, img in enumerate(images):
            img_dict = img if isinstance(img, dict) else img.model_dump()
            url = img_dict["url"]
            alt = img_dict.get("alt_text")
            heading = img_dict.get("nearest_heading")

            # Check cache to avoid repeatedly downloading/processing the same image
            if url in self._description_cache:
                description = self._description_cache[url]
            else:
                description = self.vision_provider.describe_image(
                    image_url=url, alt_text=alt, context_heading=heading
                )
                if description:
                    self._description_cache[url] = description
                    self._save_description_cache()

            if not description:
                continue

            chunk_id = f"{article_id}-img-{idx}"
            chunk_text = (
                f"Article: {article_title}\n"
                f"Source Image: {url}\n"
                f"Section: {heading or 'General'}\n"
                f"Image Description: {description}"
            )
            metadata = {
                "chunk_id": chunk_id,
                "source_type": "article_screenshot",
                "article_id": article_id,
                "title": f"Screenshot: {article_title}",
                "source_url": canonical_url,
                "image_url": url,
                "heading": heading,
                "chunk_index": idx,
                "content_hash": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
            }

            image_chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "metadata": metadata,
            })

        return image_chunks
