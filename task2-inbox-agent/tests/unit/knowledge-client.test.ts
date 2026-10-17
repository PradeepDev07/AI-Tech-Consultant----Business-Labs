import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { KnowledgeClient } from "../../src/knowledge-client/knowledge-client.js";

describe("KnowledgeClient", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("should query Task 1 and parse successful response and citations", async () => {
    const mockResponse = {
      request_id: "req_123",
      question: "How do I setup Stripe?",
      answer: "Go to Settings > Payment Gateways.",
      abstained: false,
      abstention_reason: null,
      citations: [
        {
          article_id: "art_stripe",
          article_title: "Stripe Setup",
          source_url: "https://support.brilliantdirectories.com/stripe",
          excerpt: "Stripe setup details",
        },
      ],
      retrieval_metadata: {},
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    } as any);

    const client = new KnowledgeClient({
      baseUrl: "http://localhost:8000",
      timeoutMs: 1000,
      maxRetries: 1,
    });

    const result = await client.queryKnowledge("How do I setup Stripe?");

    expect(result.success).toBe(true);
    expect(result.abstained).toBe(false);
    expect(result.answer).toBe("Go to Settings > Payment Gateways.");
    expect(result.citations.length).toBe(1);
    expect(result.citations[0].article_title).toBe("Stripe Setup");
  });

  it("should not retry on client error (HTTP 400)", async () => {
    let callCount = 0;
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++;
      return {
        ok: false,
        status: 400,
        text: async () => "Bad request",
      } as any;
    });

    const client = new KnowledgeClient({
      baseUrl: "http://localhost:8000",
      timeoutMs: 1000,
      maxRetries: 3,
    });

    const result = await client.queryKnowledge("Invalid query");

    expect(callCount).toBe(1); // Did not repeat retries
    expect(result.success).toBe(false);
    expect(result.abstained).toBe(true);
  });

  it("should retry on 500 error and return safe abstention upon exhaustion", async () => {
    let callCount = 0;
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++;
      return {
        ok: false,
        status: 500,
        headers: new Headers(),
        text: async () => "Internal error",
      } as any;
    });

    const client = new KnowledgeClient({
      baseUrl: "http://localhost:8000",
      timeoutMs: 1000,
      maxRetries: 2,
      baseDelayMs: 10,
    });

    const result = await client.queryKnowledge("Query during outage");

    expect(callCount).toBe(2);
    expect(result.success).toBe(false);
    expect(result.abstained).toBe(true);
    expect(result.abstentionReason).toContain("unavailable");
  });
});
