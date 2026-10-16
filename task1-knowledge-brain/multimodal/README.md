# Multimodal Image Processing & Understanding

## Overview

The Knowledge Brain incorporates article screenshots into its RAG pipeline to ensure visual documentation context (e.g. settings screens, webhook URLs, admin buttons) is accessible during retrieval.

## Operational Modes

1. **`VISION_PROVIDER=none` (Default MVP Mode)**:
   - Image URLs and alt text are extracted and stored with article provenance in SQLite.
   - The system **honestly reports image understanding as unavailable**.
   - No fabricated OCR or screenshot interpretations are produced.

2. **`VISION_PROVIDER=mock` (Testing & Evaluation Mode)**:
   - Synthesizes grounded visual descriptions using the extracted alt text and surrounding section heading.
   - Enables repeatable offline integration tests and evaluation benchmarks without external model dependencies.

3. **`VISION_PROVIDER=ollama` (Local Vision LLM Mode)**:
   - Configurable vision models (e.g., `llava:latest`, `moondream`) fetch image bytes and produce detailed visual captions.
   - Generates image chunks stored in the vector store with `source_type: "article_screenshot"`.

## Provenance & Safety

- **Heading Context**: Every extracted screenshot is associated with its nearest preceding heading.
- **Cache Deduplication**: Repeated image URLs across multiple articles are cached in memory to eliminate redundant downloads.
- **Error Handling**: Broken image URLs (HTTP 404/500), timeouts, and unsupported formats are gracefully logged without failing article ingestion.
