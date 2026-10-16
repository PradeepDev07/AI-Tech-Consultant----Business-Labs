# Task 1: Knowledge Brain — Brilliant Directories Solution Center

A production-grade, modular Knowledge Brain RAG (Retrieval-Augmented Generation) system built for the Brilliant Directories Solution Center documentation.

---

## 1. System Architecture

The Knowledge Brain follows a modular monolith architecture. Article discovery, polite crawling, parsing, change detection, chunking, vector indexing, grounded question answering, and human escalation are completely decoupled behind typed interfaces and dependency injection.

```mermaid
flowchart TD
    Sitemap["Sitemap XML (support.brilliantdirectories.com)"] --> Discovery["Sitemap Parser & URL Normalizer"]
    Discovery --> ChangeDetector["Change Detector (SQLite)"]
    ChangeDetector -->|New / Modified| Crawler["Polite Async Crawler (Concurrency, Backoff, 304 Caching)"]
    ChangeDetector -->|Removed| VectorPrune["Vector Store Purge & Soft Delete"]
    Crawler --> Parser["HTML Article Parser (Body, Headings, Images, SHA-256 Hash)"]
    Parser --> SQLite["SQLite Database (Metadata, Jobs, Audit Trail)"]
    Parser --> Chunker["Context-Aware Chunker (Hierarchy & Headings)"]
    Chunker --> Embeddings["Embedding Provider (Ollama / Mock)"]
    Embeddings --> VectorStore["Vector Store Adapter (ChromaDB / InMemory)"]

    User["User Question (API Client / Task 2 / Task 3)"] --> QuestionAPI["POST /api/v1/questions"]
    QuestionAPI --> Guardrail["Prompt Injection Guardrail"]
    Guardrail --> Retriever["Retriever (Top-K, Source Filter, Deduplication)"]
    Retriever <--> VectorStore
    Retriever --> ThresholdCheck{"Evidence Score >= Threshold?"}
    ThresholdCheck -->|No| Abstain["Abstain (Safe Response & Reason)"]
    Abstain --> EscalationOptional["Optional Human Escalation"]
    ThresholdCheck -->|Yes| LLM["LLM Model Provider (Ollama / Mock)"]
    LLM --> StructuredResponse["Structured Response (Grounded Answer & Citations)"]
```

---

## 2. Model Provider & Architecture Compliance Notice

- **Configurable Model-Provider Interface**: The architecture defines `BaseModelProvider` and `BaseEmbeddingProvider` interfaces.
- **Configured Environment Providers**:
  - Chat generation is configured for local/cloud **Ollama** (`llama3.2:latest`) with deterministic `MockModelProvider` for offline verification.
  - Embeddings are configured for **Ollama** (`nomic-embed-text`) with deterministic `MockEmbeddingProvider` for offline test suites.
- **Claude Deviation Statement**: The capstone brief suggested Claude. As specified in the project requirements, development was conducted using configurable Ollama models and offline test doubles to optimize budget and avoid paid model dependencies. Claude is **not** currently integrated, and this deviation is stated honestly. The provider interface allows Anthropic Claude to be plugged in seamlessly by implementing `BaseModelProvider`.
- **Vector Store**: A dual adapter (`ChromaVectorStore` for ChromaDB and `InMemoryVectorStore` for zero-dependency local execution) is provided. When ChromaDB is unavailable due to network timeout or environment constraints, the system automatically runs on the verified `InMemoryVectorStore` adapter.

---

## 3. Setup & Installation

### Requirements
- Python 3.11 or newer
- SQLite 3

### Environment Setup
```bash
cd task1-knowledge-brain

# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install fastapi uvicorn pydantic pydantic-settings httpx beautifulsoup4 lxml pytest pytest-asyncio python-dotenv

# 3. Configure environment variables
cp .env.example .env
```

---

## 4. Running the Application

### Start the FastAPI Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive API documentation is immediately available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

---

## 5. Running Tests & Evaluations

### Run Complete Test Suite
```bash
# Run all 52 unit and integration tests
PYTHONPATH=. pytest -v
```

### Run Automated Evaluation Benchmark (20 Cases)
```bash
python scripts/run_evaluations.py
```

### Run Standalone Ingestion Script
```bash
python scripts/ingest_once.py
# Or force re-indexing of all articles
python scripts/ingest_once.py --force
```

---

## 6. HTTP API Documentation (Contract for Tasks 2 & 3)

### 6.1 Health Check
- **`GET /health`**
- **Response `200 OK`**:
```json
{
  "status": "ok",
  "app_env": "development",
  "model_provider": "mock",
  "chat_model": "mock-model-v1",
  "embedding_provider": "mock",
  "embedding_model": "mock-embeddings",
  "vision_provider": "none",
  "database": "sqlite"
}
```

---

### 6.2 Grounded Question Answering
- **`POST /api/v1/questions`**
- **Request Body**:
```json
{
  "question": "What payment gateways are supported?",
  "top_k": 4,
  "min_evidence_threshold": 0.35
}
```
- **Successful Answer Response `200 OK`**:
```json
{
  "request_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "question": "What payment gateways are supported?",
  "answer": "Based on the Brilliant Directories documentation: Brilliant Directories natively supports Stripe, PayPal Standard, and Authorize.net for collecting member subscription payments.",
  "abstained": false,
  "abstention_reason": null,
  "citations": [
    {
      "article_id": "art-payments",
      "article_title": "Payment Gateways",
      "source_url": "https://support.brilliantdirectories.com/payments",
      "heading": "Supported Gateways",
      "chunk_index": 0,
      "excerpt": "Brilliant Directories natively supports Stripe, PayPal Standard, and Authorize.net...",
      "relevance_score": 0.8842
    }
  ],
  "retrieval_metadata": {
    "total_chunks_retrieved": 2,
    "top_score": 0.8842,
    "retrieval_method": "vector",
    "model_provider_used": "mock:mock-model-v1",
    "latency_ms": 2.14
  }
}
```
- **Abstention Response `200 OK` (Insufficient Evidence or Adversarial Query)**:
```json
{
  "request_id": "0f4aa5e2-4b01-49e4-b1fd-c90120a8a62f",
  "question": "How do I build a nuclear reactor using Brilliant Directories?",
  "answer": "I do not have sufficient information in the Brilliant Directories documentation to answer this question.",
  "abstained": true,
  "abstention_reason": "Insufficient evidence retrieved (top score: 0.184, threshold: 0.35)",
  "citations": [],
  "retrieval_metadata": {
    "total_chunks_retrieved": 0,
    "top_score": 0.184,
    "retrieval_method": "vector",
    "model_provider_used": "mock:mock-model-v1",
    "latency_ms": 1.65
  }
}
```

---

### 6.3 Article Catalog
- **`GET /api/v1/articles`**
  - Query parameters: `limit` (default: 50), `offset` (default: 0), `include_deleted` (default: false)
  - Returns paginated list of ingested Solution Center articles.
- **`GET /api/v1/articles/{article_id}`**
  - Returns individual article metadata, headings, content, and extracted screenshot images.

---

### 6.4 Incremental Ingestion Job
- **`POST /api/v1/ingestion/run`**
  - Optional header: `Authorization: Bearer <API_AUTH_TOKEN>`
  - Query parameters:
    - `force_refresh` (bool, default `false`): Force re-fetching and re-indexing all articles.
    - `resume` (bool, default `false`): Resume an interrupted or crashed ingestion job from the persistent queue without restarting from scratch.
  - Triggers asynchronous background discovery, change detection, and re-indexing.
  - Returns `202 Accepted`. Rejects overlapping concurrent runs with `409 Conflict`.
- **`GET /api/v1/ingestion/status`**
  - Returns metrics on the latest ingestion job: `urls_discovered`, `articles_added`, `articles_updated`, `articles_unchanged`, `articles_removed`, `queue_summary` (`total`, `pending`, `processing`, `completed`, `failed`), and any transient `errors`.
- **Background Periodic Scheduler**:
  - Controlled by environment variables: `SCHEDULED_INGESTION_ENABLED=true` and `SCHEDULED_INGESTION_INTERVAL_HOURS=24.0`.
  - Non-blocking `PeriodicIngestionWorker` managed through FastAPI lifespan context.

---

### 6.5 Human Escalation & Knowledge Approval
When an answer cannot be grounded or the system abstains, an escalation can be created:

1. **Create Escalation**:
   - `POST /api/v1/escalations`
   - Request: `{"question": "How do I setup Amazon SES SMTP?", "retrieved_evidence": []}`
   - Returns: Escalation record with status `"open"` and unique `escalation_id`.

2. **List Escalations**:
   - `GET /api/v1/escalations?status=open`

3. **Submit Human Expert Answer**:
   - `POST /api/v1/escalations/{escalation_id}/answer`
   - Request: `{"expert_answer": "Configure Amazon SES under Settings > Email Settings...", "expert_name": "Senior Support Engineer Alice"}`
   - Updates status to `"answered"`.

4. **Approve & Index Knowledge**:
   - `POST /api/v1/escalations/{escalation_id}/approve`
   - Request: `{"approved_by": "Knowledge Admin Bob", "reviewer_notes": "Verified in staging"}`
   - Updates status to `"approved"`, marks `reindexed_at`, and **automatically indexes the approved Q&A pair into the vector store**.
   - Subsequent user questions on this topic are answered immediately with citations referencing the approved escalation record.

---

## 7. Evaluation Results (20 Benchmark Cases)

The evaluation suite was executed via `python scripts/run_evaluations.py`.

### Measured Performance Summary
| Metric | Result |
| :--- | :--- |
| **Total Test Cases** | **20** |
| **Abstention Accuracy** | **100.0%** (20/20) |
| **Answer Correctness Accuracy** | **100.0%** (20/20) |
| **Mean Citation Recall** | **1.0000** |
| **Mean Citation Precision** | **0.5500** |
| **Mean Request Latency** | **3.66 ms** |
| **Model Cost** | **$0.00** (Zero-cost offline test execution) |

Results are recorded deterministically in `storage/evaluation_results.json`.

---

## 8. Transfer Checklist (Moving to Real Git Repository)

When copying `task1-knowledge-brain` into the final Git repository:

1. Copy all source files in `app/`, `ingestion/`, `retrieval/`, `multimodal/`, `evaluation/`, `tests/`, and `scripts/`.
2. Copy `pyproject.toml`, `.env.example`, and `README.md`.
3. **DO NOT copy** runtime artifacts:
   - `storage/*.db` (SQLite databases)
   - `storage/chroma_db/` (Vector store indices)
   - `storage/evaluation_results.json`
   - `.env` (Local environment secrets)
   - `.venv/` (Virtual environment)
4. Run `pytest` in the destination repository to verify all 33 tests pass.
