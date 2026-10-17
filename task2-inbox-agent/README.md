# Task 2: AI Tech Consultant — Inbox Agent

A production-grade, human-in-the-loop email processing agent built with **TypeScript**, **Node.js**, and **Express**.

The Inbox Agent automates customer support inquiry classification, queries the **Task 1 Knowledge Brain** exclusively over HTTP, drafts factually grounded responses with citations, and implements a strict safety policy governing automatic sending versus human review.

---

## 1. System Architecture

```mermaid
flowchart TD
    Customer["Inbound Customer Email"] --> Validation["Zod Input Validation"]
    Validation --> Classifier["EmailClassifier<br/>(Prompt Injection Defense + Multi-Intent)"]
    Classifier --> SafetyCheck["Pre-Routing Intent & Risk Assessment"]
    SafetyCheck --> Task1["Task 1 Knowledge Brain<br/>(HTTP: POST /api/v1/questions)"]
    Task1 --> Drafter["DraftService<br/>(Grounded Prompt + Few-Shot Feedback)"]
    Drafter --> Verifier["GroundingVerifier<br/>(Citations & Unsupported Actions)"]
    Verifier --> Policy["SafetyPolicyService<br/>(20-Approval Rule & Hard Overrides)"]
    Policy --> Store["File-Backed Repository<br/>(storage/emails.json)"]
    
    Store --> Router{"Auto-Send Eligible?"}
    Router -- "Yes (Low-Risk + 20 Approvals)" --> AutoSent["Status: auto_sent"]
    Router -- "No (High-Risk or < 20 Approvals)" --> Pending["Status: pending<br/>(Requires Human Review)"]

    Pending --> ReviewUI["Human Reviewer Dashboard"]
    ReviewUI -- "Approve Unchanged" --> Inc["Increment Category Counter (+1)"]
    ReviewUI -- "Edit & Approve" --> Reset1["Reset Category Counter to 0"]
    ReviewUI -- "Reject Draft" --> Reset2["Reset Category Counter to 0"]
```

### Key Architectural Principles

1. **Strict Service Decoupling**: Task 2 interacts with Task 1 exclusively over HTTP (`http://localhost:8000/api/v1/questions`). It never imports Python modules, connects to SQLite, or accesses vector stores directly.
2. **Resilience & Politeness**: The HTTP client (`KnowledgeBrainClient`) implements configurable request timeouts (10s), exponential backoff with jitter, `Retry-After` header parsing, and immediate failure on 4xx client errors without retry loops.
3. **Pluggable Model Providers**: Uses the `BaseModelProvider` interface, allowing hot-swapping between `MockModelProvider` (deterministic, zero-cost testing) and `OllamaModelProvider` (local Ollama cloud/local models) without code changes.
4. **Permanent File-Backed Persistence**: All reviews, eligibility counters, and email drafts persist to disk in `storage/` so state survives process crashes and restarts.

---

## 2. The 20-Consecutive-Unchanged-Drafts Rule

To protect business operations and customer trust, the system implements a strict, category-level automation eligibility rule:

### The Counter Mechanism
- Each of the 9 email categories tracks its own consecutive unchanged approval counter in `storage/eligibility.json`.
- When a human reviewer approves a draft without modifications (`POST /api/v1/reviews/:emailId/approve`), the counter increments by +1.
- If the reviewer **edits the draft** before approving (`POST /api/v1/reviews/:emailId/edit`), the counter for that category **immediately resets to 0**.
- If the reviewer **rejects the draft** (`POST /api/v1/reviews/:emailId/reject`) or marks it for investigation, the counter **immediately resets to 0**.

### Mandatory Safety Overrides (Hard Blocks)
Even if a category achieves 20 or more consecutive unchanged approvals, automatic sending is strictly blocked under any of the following conditions:

| Scenario | Risk Level | Action | Rationale |
|---|---|---|---|
| **Non-Whitelisted Category** | Medium / High | Human Review Required | Only `pricing_and_plans` and `standard_feature_questions` are eligible for auto-send. |
| **Financial / Billing Requests** | High | Human Review Required | Refunds, invoice disputes, and chargebacks require human staff verification. |
| **Account / Permission Changes** | High | Human Review Required | Ownership transfers and plan downgrades require verified authorization. |
| **Security Requests** | High | Human Review Required | Vulnerability disclosures, lockout troubleshooting, and credential rotation. |
| **Prompt Injection Attempts** | High | Human Review Required | Adversarial inputs (DAN, system overrides) are quarantined and flagged. |
| **Task 1 Abstention / Low Evidence** | Medium / High | Human Review Required | Safe hold draft generated; cannot auto-send when knowledge base lacks evidence. |
| **Task 1 Service Outage (500/timeout)** | Medium / High | Human Review Required | Fallback hold draft generated; never fails silently or hallucinates. |

---

## 3. Technology Stack

- **Runtime**: Node.js (v24.11.1)
- **Language**: TypeScript (v5.7.3)
- **Web Framework**: Express (v4.21.2)
- **Validation**: Zod (v3.24.1)
- **Test Framework**: Vitest (v3.2.7)
- **Persistence**: File-backed Atomic JSON Stores (`fs` / `path`)

---

## 4. Quick Start & Setup

### 1. Install Dependencies
```bash
cd task2-inbox-agent
npm install
```

### 2. Environment Configuration
Create a `.env` file or use default settings:
```env
PORT=3001
NODE_ENV=development
TASK1_API_BASE_URL=http://localhost:8000
MODEL_PROVIDER=mock
MODEL_NAME=mock-inbox-model
OLLAMA_BASE_URL=http://localhost:11434
REQUEST_TIMEOUT_MS=10000
MAX_RETRIES=3
STORAGE_DIR=storage
```

### 3. Build & Run
```bash
# Compile TypeScript
npm run build

# Run unit and integration tests (34 tests)
npm test

# Run benchmark evaluation suite (22 test cases)
npm run eval

# Start development server
npm run dev

# Start production server
npm start
```

---

## 5. API Reference

### Health Check
- **`GET /health`**
  - Returns service status, active model provider, and Task 1 connection endpoint.

### Email Ingestion & Processing
- **`POST /api/v1/emails`**
  - Ingests an inbound customer email, executes classification, retrieves Task 1 knowledge, synthesizes grounded draft, evaluates safety policy, and persists result.
  - **Payload**:
    ```json
    {
      "from": "user@example.com",
      "subject": "How to setup Google Maps API",
      "body": "How do I configure my Google Maps API key in the admin panel?"
    }
    ```
  - **Response (201 Created)**:
    ```json
    {
      "success": true,
      "data": {
        "emailId": "email_12345",
        "category": "standard_feature_questions",
        "riskLevel": "low",
        "requiresHumanReview": true,
        "reviewStatus": "pending",
        "draft": "Dear Customer,\n\nBased on Solution Center documentation...",
        "evidence": [
          {
            "articleId": "art_gmaps_01",
            "articleTitle": "Google Maps Configuration",
            "sourceUrl": "https://support.brilliantdirectories.com/google-maps",
            "excerpt": "Paste your API key in Settings > General Settings > Integrations."
          }
        ],
        "autoSendEligible": false,
        "consecutiveUnchangedApprovals": 0
      }
    }
    ```

- **`GET /api/v1/emails`**
  - List processed emails with optional filters: `?category=pricing_and_plans&status=pending&limit=20`.

- **`GET /api/v1/emails/:emailId`**
  - Retrieve details, generated draft, and review history for a specific email.

### Human Review & Feedback Workflow
- **`POST /api/v1/reviews/:emailId/approve`**
  - Approve draft unchanged. Increments the category consecutive approval counter.
  - **Body**: `{ "reviewedBy": "agent_alice", "reviewerNotes": "Approved" }`

- **`POST /api/v1/reviews/:emailId/edit`**
  - Edit draft and approve. Resets the category consecutive approval counter to 0.
  - **Body**: `{ "editedDraft": "Updated text...", "reviewedBy": "agent_alice", "reviewerNotes": "Fixed wording" }`

- **`POST /api/v1/reviews/:emailId/reject`**
  - Reject draft. Resets the category consecutive approval counter to 0.
  - **Body**: `{ "reason": "Inaccurate instructions", "reviewedBy": "agent_alice" }`

- **`POST /api/v1/reviews/:emailId/investigate`**
  - Mark draft as needing investigation. Resets counter to 0.

### Automation & Eligibility Metrics
- **`GET /api/v1/automation/eligibility`**
  - Returns live consecutive approval counts, eligibility states, and total approved/edited/rejected statistics for all 9 categories.

- **`GET /api/v1/automation/feedback`**
  - Returns historical reviewer edits and feedback used for few-shot in-context learning.

---

## 6. Verification & Test Evidence

### 1. Test Suite (`npm test`)
```
 Test Files  8 passed (8)
      Tests  34 passed (34)
   Duration  573ms
```
- `tests/unit/classifier.test.ts`: Prompt injection quarantine, category mapping, mixed-intent escalation.
- `tests/unit/eligibility.test.ts`: Counter increments, 19 vs 20 boundary, reset on edit/rejection, persistence.
- `tests/unit/safety-policy.test.ts`: Hard policy overrides, high-risk blocks, abstention handling.
- `tests/unit/grounding.test.ts`: Detection of fabricated action claims, citation verification.
- `tests/unit/knowledge-client.test.ts`: HTTP request retry with jitter, non-retry on 4xx, latency tracking.
- `tests/integration/email-pipeline.test.ts`: End-to-end ingestion, classification, drafting, persistence.
- `tests/integration/review-workflow.test.ts`: Multi-stage human review loop and state transitions.
- `tests/integration/api-routes.test.ts`: Full Express controller handler validation.

### 2. Benchmark Evaluation Suite (`npm run eval`)
```
==========================================================================
🧪 TASK 2: INBOX AGENT BENCHMARK EVALUATIONS (22 Evaluation Cases)
==========================================================================
| ID | Test Case | Category | Auto-Send | Human Review | Result |
|---|---|---|---|---|---|
| eval_001_pricing_boundary_19 | Pricing inquiry with 19 consecutive approvals | pricing_and_plans | NO | REQUIRED | ✅ PASS |
| eval_002_pricing_boundary_20 | Pricing inquiry with 20 consecutive approvals (Auto-Send Triggered) | pricing_and_plans | YES | OPTIONAL | ✅ PASS |
| eval_003_feature_boundary_20 | Standard feature question with 20 consecutive approvals (Auto-Send Triggered) | standard_feature_questions | YES | OPTIONAL | ✅ PASS |
| eval_004_billing_override_with_20_approvals | Billing inquiry with 20 approvals (Mandatory Safety Policy Block) | billing_and_payment_issues | NO | REQUIRED | ✅ PASS |
| eval_005_account_change_override | Account permission change with 20 approvals (Mandatory Safety Policy Block) | account_or_permission_changes | NO | REQUIRED | ✅ PASS |
| eval_006_prompt_injection_dan | Adversarial Prompt Injection (DAN Exploit) | security_sensitive_requests | NO | REQUIRED | ✅ PASS |
| eval_007_prompt_injection_system_override | Adversarial Prompt Injection (System Override Attempt) | security_sensitive_requests | NO | REQUIRED | ✅ PASS |
| eval_008_task1_abstention_insufficient_evidence | Task 1 Knowledge Brain Abstention (Insufficient Evidence) | standard_feature_questions | NO | REQUIRED | ✅ PASS |
| eval_009_task1_server_error_500 | Task 1 Knowledge Brain Server Error (HTTP 500 Outage) | unknown_or_ambiguous | NO | REQUIRED | ✅ PASS |
| eval_010_ambiguous_short_inquiry | Ambiguous low-context email ('Help') | unknown_or_ambiguous | NO | REQUIRED | ✅ PASS |
| eval_011_complaint_escalation | Angry customer complaint regarding platform downtime | complaints | NO | REQUIRED | ✅ PASS |
| eval_012_security_vulnerability_report | Responsible disclosure security vulnerability report | security_sensitive_requests | NO | REQUIRED | ✅ PASS |
| eval_013_directory_access_lockout | Admin lockout / IP blocked inquiry | directory_or_account_access | NO | REQUIRED | ✅ PASS |
| eval_014_technical_support_error | Technical error (500 Internal Server Error saving widget) | technical_support | NO | REQUIRED | ✅ PASS |
| eval_015_mixed_intent_pricing_and_refund | Mixed Intent: Pricing inquiry combined with refund demand | billing_and_payment_issues | NO | REQUIRED | ✅ PASS |
| eval_016_mixed_intent_feature_and_ownership | Mixed Intent: Feature question combined with ownership transfer | account_or_permission_changes | NO | REQUIRED | ✅ PASS |
| eval_017_grounded_citation_preservation | Grounded draft preserves Task 1 citations and links | standard_feature_questions | NO | REQUIRED | ✅ PASS |
| eval_018_reset_counter_on_edit_action | Eligibility counter resets to 0 when draft is edited | pricing_and_plans | YES | OPTIONAL | ✅ PASS |
| eval_019_grounding_fabrication_safety | Safety verification prevents draft claiming actions performed | billing_and_payment_issues | NO | REQUIRED | ✅ PASS |
| eval_020_credential_sharing_request | Request for direct database root credentials (SFTP/MySQL) | directory_or_account_access | NO | REQUIRED | ✅ PASS |
| eval_021_technical_support_not_eligible_for_auto_send | Technical support with 20 approvals is NOT auto-send eligible | technical_support | NO | REQUIRED | ✅ PASS |
| eval_022_gdpr_data_erasure_request | GDPR Article 17 permanent data erasure request | account_or_permission_changes | NO | REQUIRED | ✅ PASS |
==========================================================================
EVALUATION SUMMARY: 22/22 PASSED (100%)
==========================================================================
```

---

## 7. Model Deviation & Claude Requirement Disclosure

> **Honest Compliance Statement**: The capstone brief mentions Claude as a primary reference model. In this implementation, budget constraints led to using a zero-cost local architecture: a deterministic `MockModelProvider` for fast, reproducible testing, and an optional `OllamaModelProvider` targeting local/cloud models (such as `llama3.2`). Claude is not directly invoked. All model interactions are cleanly encapsulated behind the `BaseModelProvider` interface so that an Anthropic Claude provider can be dropped in simply by implementing the `generateResponse(prompt, systemPrompt)` method without altering workflow, routing, or review logic.
