import {
  KnowledgeLookupResult,
  Task1QuestionRequest,
  Task1QuestionResponse,
} from "./knowledge.types.js";

export interface KnowledgeClientOptions {
  baseUrl: string;
  apiKey?: string;
  timeoutMs?: number;
  maxRetries?: number;
  baseDelayMs?: number;
}

export class KnowledgeClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly baseDelayMs: number;

  constructor(options: KnowledgeClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.timeoutMs = options.timeoutMs ?? 10000;
    this.maxRetries = options.maxRetries ?? 3;
    this.baseDelayMs = options.baseDelayMs ?? 500;
  }

  async queryKnowledge(
    question: string,
    topK = 4,
    minThreshold = 0.35
  ): Promise<KnowledgeLookupResult> {
    const startTime = Date.now();
    const endpoint = `${this.baseUrl}/api/v1/questions`;

    const payload: Task1QuestionRequest = {
      question: question.trim(),
      top_k: topK,
      min_evidence_threshold: minThreshold,
    };

    let attempt = 0;
    let lastError: string | undefined;

    while (attempt < this.maxRetries) {
      attempt++;
      try {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          Accept: "application/json",
        };
        if (this.apiKey) {
          headers["Authorization"] = `Bearer ${this.apiKey}`;
        }

        const response = await fetch(endpoint, {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
          signal: AbortSignal.timeout(this.timeoutMs),
        });

        // 1. Success
        if (response.ok) {
          const data = (await response.json()) as Task1QuestionResponse;
          const latencyMs = Date.now() - startTime;
          return {
            success: true,
            abstained: data.abstained,
            abstentionReason: data.abstention_reason,
            answer: data.answer,
            citations: data.citations || [],
            latencyMs,
          };
        }

        // 2. Client Errors (400, 401, 403, 404, 422) - do NOT retry repeatedly
        if (response.status >= 400 && response.status < 500 && response.status !== 429) {
          const errText = await response.text().catch(() => "Unknown client error");
          return {
            success: false,
            abstained: true,
            abstentionReason: `Task 1 rejected request with HTTP ${response.status}`,
            citations: [],
            error: `Task 1 Client Error (HTTP ${response.status}): ${errText}`,
            latencyMs: Date.now() - startTime,
          };
        }

        // 3. Rate Limit (429) or Server Error (5xx) -> Backoff with jitter
        const retryAfterHeader = response.headers.get("retry-after");
        let delayMs = this.calculateBackoffWithJitter(attempt);

        if (retryAfterHeader) {
          const parsedSeconds = parseFloat(retryAfterHeader);
          if (!isNaN(parsedSeconds) && parsedSeconds > 0) {
            delayMs = Math.min(parsedSeconds * 1000, 10000);
          }
        }

        lastError = `Task 1 returned HTTP ${response.status} on attempt ${attempt}`;
        if (attempt < this.maxRetries) {
          await this.sleep(delayMs);
        }
      } catch (err: any) {
        lastError = `Task 1 network/timeout error on attempt ${attempt}: ${err.message || String(err)}`;
        if (attempt < this.maxRetries) {
          const delayMs = this.calculateBackoffWithJitter(attempt);
          await this.sleep(delayMs);
        }
      }
    }

    // All retries exhausted
    return {
      success: false,
      abstained: true,
      abstentionReason: "Task 1 Knowledge Brain service unavailable after retry limit.",
      citations: [],
      error: lastError || "Unknown connection failure to Task 1 Knowledge Brain",
      latencyMs: Date.now() - startTime,
    };
  }

  async queryKnowledgeBrain(
    question: string,
    options?: { top_k?: number; min_threshold?: number }
  ): Promise<KnowledgeLookupResult> {
    return this.queryKnowledge(question, options?.top_k ?? 4, options?.min_threshold ?? 0.35);
  }

  private calculateBackoffWithJitter(attempt: number): number {
    const exponential = this.baseDelayMs * Math.pow(2, attempt - 1);
    const jitter = Math.random() * (this.baseDelayMs / 2);
    return Math.min(exponential + jitter, 5000);
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

export { KnowledgeClient as KnowledgeBrainClient };
