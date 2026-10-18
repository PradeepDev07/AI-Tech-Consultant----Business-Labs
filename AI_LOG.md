# AI Engineering & Development Log (AI_LOG.md)

This log records the development lifecycle, AI interactions, prompts, architectural decisions, modifications, and verification milestones for the **AI Tech Consultant** capstone project.

---

## 1. Development Timeline & Milestones

### Milestone 1: Task 1 — Knowledge Brain Implementation
- **Goal**: Build grounded RAG knowledge engine crawling Brilliant Directories documentation, providing vector search, citations, and abstention/escalation workflows.
- **Key Engineering Steps**:
  1. Implemented polite crawler with sitemap parsing, domain restriction, and retry backoff.
  2. Implemented change detector using SHA-256 content hashing and conditional HTTP headers (`ETag`, `If-Modified-Since`).
  3. Built context-aware chunker preserving header hierarchy and multimodal image references.
  4. Implemented vector storage abstraction (`BaseVectorStore`) with ChromaDB and `InMemoryVectorStore` fallback.
  5. Built `AnswerService` with strict citation verification, explicit abstention logic, and prompt injection defense.
  6. Implemented human escalation lifecycle with re-indexing into vector memory.
  7. Constructed benchmark evaluation suite with 20 test cases in `evaluation/dataset.json`.
- **Verification Result**: 33/33 Pytest tests passing; 20/20 benchmark evaluation cases passing (100% abstention accuracy, 2.06ms mean latency).

### Milestone 2: Task 2 — Inbox Agent Implementation
- **Goal**: Implement autonomous email processing agent in TypeScript/Node.js communicating with Task 1 strictly over HTTP, featuring safeguarded 20-approval auto-send eligibility and human feedback loops.
- **Key Engineering Steps**:
  1. Built Express.js architecture in TypeScript with strict typing.
  2. Designed `KnowledgeClient` with bounded retries, full jitter exponential backoff, and non-retry on 4xx errors.
  3. Built 8-category classifier with adversarial prompt injection quarantine.
  4. Implemented `GroundingVerifier` preventing false operational claims (e.g. false refunds or password resets).
  5. Implemented `EligibilityService` tracking independent consecutive unchanged approvals per category.
  6. Implemented `SafetyPolicyService` enforcing hard policy blocks on billing, security, and access categories.
  7. Built `FeedbackService` capturing reviewer edits and injecting approved examples as few-shot context into future prompts.
  8. Created 50 synthetic customer emails in `data/sample-emails.json`.
  9. Built benchmark evaluation runner with 22 test cases.
- **Verification Result**: 34/34 Vitest tests passing; 22/22 benchmark evaluation cases passing; `tsc` compiling with 0 errors.

### Milestone 3: Task 3 — Meeting to Scope Agent Implementation
- **Goal**: Implement discovery transcript scoper in Python/FastAPI extracting traceable requirements, validating feasibility against Task 1 HTTP API, generating PERT estimates, client proposals, and tracking scope changes.
- **Key Engineering Steps**:
  1. Defined Pydantic v2 domain schemas enforcing verbatim `source_quote` traceability and status assignment (`confirmed`, `assumed`, `ambiguous`, `requires_clarification`).
  2. Implemented adversarial prompt injection defense neutralizing hidden instructions inside raw transcripts.
  3. Built `FeasibilityAgent` querying Task 1 HTTP API, categorizing requirements as `SUPPORTED`, `BLOCKED`, or `INSUFFICIENT`.
  4. Built `EstimationAgent` enforcing mathematical consistency ($\text{total} = \sum \text{tasks}$) and unpriced commercial terms (`unpriced_rates_unknown`).
  5. Built `ProposalAgent` generating cohesive proposals directly from the scope deliverable matrix.
  6. Built `ScopeDiffService` detecting added, removed, modified, and contradictory requirements, calculating delta hours.
  7. Implemented `ApprovalService` managing the immutable version lifecycle (`DRAFT` $\rightarrow$ `APPROVED` $\rightarrow$ `SUPERSEDED` $\rightarrow$ v2).
  8. Created 3 synthetic discovery meeting transcripts in `transcripts/sample_transcripts/`.
  9. Built benchmark evaluation runner with 24 test cases.
- **Verification Result**: 11/11 Pytest tests passing; 24/24 benchmark evaluation cases passing (100%).

### Milestone 4: Capstone Audit, Integration & Defense Alignment
- **Goal**: Comprehensive repository audit, cross-task boundary verification, model-provider transparency, and defense documentation.
- **Key Engineering Steps**:
  1. Formulated 42 comprehensive technical defense questions and answers in root `QA.md`.
  2. Built Requirement Traceability Matrix in `CAPSTONE_AUDIT.md` tracking 35 specific requirements.
  3. Created root `DESIGN.md` and `EVALS.md` with full architecture diagrams and empirical comparison benchmarks.
  4. Seeded default Task 1 SQLite database (`knowledge_brain.db`) with 11 canonical documentation articles for instant queryability.
  5. Verified all 78 automated unit/integration tests and 66 benchmark evaluation scenarios across the entire repository.

---

## 2. Key Architectural Decisions & Rationales

1. **HTTP API Isolation (Rule Compliance)**:
   - *Decision*: Strictly forbid Python imports between tasks. Tasks 2 and 3 connect to Task 1 exclusively via HTTP REST endpoints (`POST http://localhost:8000/api/v1/questions`).
   - *Rationale*: Guarantees true service decoupling, simulating independent microservice deployments.
2. **Deterministic Mock Double for CI/CD & Honest Disclosure**:
   - *Decision*: Anthropic Claude requirement replaced with zero-cost deterministic mock providers and local Ollama adapters.
   - *Rationale*: Completely prevents fabricated model usage or hidden API costs, providing 100% reproducible test execution.
3. **Unpriced Commercial Terms**:
   - *Decision*: Scopes and proposals leave hourly rates and total project costs unpriced (`currency_rate_status = "unpriced_rates_unknown"`).
   - *Rationale*: Eliminates the catastrophic legal risk of an AI agent committing a consultancy to unapproved pricing or timelines.
4. **Permanent Safety Gate for High-Risk Inquiries**:
   - *Decision*: Financial, account permission, and security emails can NEVER auto-send, regardless of how many times they have been reviewed.
   - *Rationale*: Autonomous sending must be reserved exclusively for low-risk informational queries.

---

## 3. Tool & Verification Commands Summary

```bash
# Task 1: Pytest Suite (42 tests)
task1-knowledge-brain/.venv/bin/python -m pytest task1-knowledge-brain/tests/ -v

# Task 1: Benchmark Suite (20 cases)
task1-knowledge-brain/.venv/bin/python task1-knowledge-brain/scripts/run_evaluations.py

# Task 2: Vitest Suite (41 tests)
cd task2-inbox-agent && npm test

# Task 2: Benchmark Suite (22 cases)
cd task2-inbox-agent && npm run eval

# Task 2: TypeScript Strict Compilation
cd task2-inbox-agent && npm run build

# Task 3: Pytest Suite (18 tests)
PYTHONPATH=task3-meeting-to-scope task1-knowledge-brain/.venv/bin/python -m pytest task3-meeting-to-scope/tests/ -v

# Task 3: Benchmark Suite (24 cases)
task1-knowledge-brain/.venv/bin/python task3-meeting-to-scope/evaluation/run_evaluation.py
```

---

## 7. Unified AI Providers & Capstone Dashboard Extension

### Actions Taken
1. **Unified AI Model-Provider System**:
   - Implemented `ClaudeModelProvider` across all three tasks connecting to Anthropic Messages API (`https://api.anthropic.com/v1/messages`).
   - Implemented `OllamaModelProvider` health checks with automatic tag discovery from `/api/tags`.
   - Created thread-safe `ProviderManager` instances across Tasks 1, 2, and 3 exposing uniform REST endpoints (`GET /api/v1/provider`, `POST /api/v1/provider/select`, `POST /api/v1/provider/test`).
   - Added `DelegatingModelProvider` in Task 2 to enable real-time runtime provider switching without service restarts.
2. **Interactive Single-Page Dashboard**:
   - Created `task1-knowledge-brain/app/static/index.html` (zero-build Tailwind SPA).
   - Top Provider Bar: live switching between Mock, Ollama, and Claude, latency probes, model selection, and one-click multi-task sync.
   - Three dedicated task consoles: Task 1 (RAG Q&A with citations), Task 2 (Email triage, 20-approval tracker, review actions), Task 3 (Discovery transcripts, requirements extraction, PERT hours, proposals).
3. **Automated Verification**:
   - Expanded unit tests from 78 to **101 tests** (Task 1: 42, Task 2: 41, Task 3: 18) — all 101 passing.
   - Verified all **66 benchmark evaluation scenarios** (Task 1: 20, Task 2: 22, Task 3: 24) — 100% pass rate.
   - Zero-cost testability preserved: Mock mode remains the default offline double.

---

## 8. Milestone 8: Live Sitemap Ingestion, In-Process Periodic Scheduler, Persistent Queue & Multimodal Caching

### Actions Taken
1. **Live Sitemap & Crawler Verification**:
   - Performed real live fetch of `https://support.brilliantdirectories.com/support/sitemap.xml`.
   - Discovered 1,699 live XML URLs (1,540 matching Solution Center article patterns).
   - Ingested sample live pages into database, verified content normalization, vector generation (14 chunks), and live retrieval.
2. **Item 1: In-Process Periodic Scheduler**:
   - Implemented `PeriodicIngestionWorker` in `task1-knowledge-brain/ingestion/scheduler.py` running on a configurable interval (`SCHEDULED_INGESTION_INTERVAL_HOURS`).
   - Integrated with FastAPI lifespan context in `task1-knowledge-brain/app/main.py` for automated startup and graceful shutdown.
3. **Item 2: Persistent Ingestion Queue Cursor**:
   - Added SQLite table `ingestion_queue` in `task1-knowledge-brain/app/services/database.py` tracking per-URL states (`pending`, `processing`, `completed`, `failed`), retries, and errors.
   - Added crash resumption support (`resume=True`) to `POST /api/v1/ingestion/run` and queue progress reporting to `GET /api/v1/ingestion/status`.
4. **Item 3: Multimodal Image Asset Disk Caching & Offline OCR Fallback**:
   - Added local disk caching in `task1-knowledge-brain/multimodal/image_processor.py` (`fetch_or_cache_image`) saving image bytes to `storage/images/` and description manifests to `descriptions.json`.
   - Implemented `OCRVisionProvider` supporting offline OCR text extraction and graceful PIL image analysis fallback.
   - Created unified `create_vision_provider()` factory matching application settings.
5. **Item 4: Storage Directory Hygiene**:
   - Removed duplicate empty root `storage/` directory and corrected relative database paths in Task 3 to resolve relative to `task3-meeting-to-scope/`.
6. **Automated Verification**:
   - Added unit test suites `test_scheduler_worker.py` and `test_ingestion_queue.py`, and updated `test_multimodal.py`.
   - Total automated tests expanded to **111 tests** (Task 1: 52, Task 2: 41, Task 3: 18) — all passing.
   - All **66 benchmark evaluation scenarios** verified (100% pass rate).
