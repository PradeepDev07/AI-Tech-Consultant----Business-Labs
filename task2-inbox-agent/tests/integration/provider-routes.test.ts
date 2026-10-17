import { describe, it, expect, beforeEach } from "vitest";
import { createProviderRouter } from "../../src/routes/provider.routes.js";
import { getProviderManager } from "../../src/providers/model-provider.js";

function createMockReqRes(reqPartial: any = {}) {
  const req: any = { body: {}, params: {}, query: {}, ...reqPartial };
  const res: any = {
    statusCode: 200,
    body: null,
    status(code: number) {
      this.statusCode = code;
      return this;
    },
    json(data: any) {
      this.body = data;
      return this;
    },
  };
  return { req, res };
}

function getHandler(router: any, path: string, method: "get" | "post") {
  const layer = router.stack.find(
    (s: any) => s.route?.path === path && s.route?.methods?.[method]
  );
  if (!layer) {
    throw new Error(`Handler not found for ${method.toUpperCase()} ${path}`);
  }
  return layer.route.stack[0].handle;
}

describe("Task 2 Provider Routes", () => {
  let router: any;

  beforeEach(async () => {
    const manager = getProviderManager();
    await manager.setActiveProvider("mock");
    router = createProviderRouter();
  });

  it("GET /api/v1/provider returns provider status without leaking secrets", async () => {
    const handler = getHandler(router, "/", "get");
    const { req, res } = createMockReqRes();
    await handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.body.active_provider_type).toBe("mock");
    expect(res.body.available_providers).toContain("mock");
    expect(res.body.available_providers).toContain("ollama");
    expect(res.body.available_providers).toContain("claude");
    expect(res.body.claude).toBeDefined();
    expect(res.body.claude.apiKey).toBeUndefined();
    expect(res.body.claude.api_key).toBeUndefined();
  });

  it("POST /api/v1/provider/test tests mock connectivity successfully", async () => {
    const handler = getHandler(router, "/test", "post");
    const { req, res } = createMockReqRes({ body: { provider: "mock" } });
    await handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.body.status).toBe("ok");
  });

  it("POST /api/v1/provider/test reports error when Claude key is missing", async () => {
    const handler = getHandler(router, "/test", "post");
    const { req, res } = createMockReqRes({ body: { provider: "claude", apiKey: "" } });
    await handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.body.status).toBe("error");
    expect(res.body.message.toLowerCase()).toContain("not configured");
  });

  it("POST /api/v1/provider/select rejects unknown providers with 400", async () => {
    const handler = getHandler(router, "/select", "post");
    const { req, res } = createMockReqRes({ body: { provider: "openai-gpt" } });
    await handler(req, res);

    expect(res.statusCode).toBe(400);
    expect(res.body.error).toContain("Invalid provider");
  });

  it("POST /api/v1/provider/select can switch to mock", async () => {
    const handler = getHandler(router, "/select", "post");
    const { req, res } = createMockReqRes({ body: { provider: "mock" } });
    await handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.active_provider).toContain("mock");
  });

  it("POST /api/v1/provider/select without Claude key returns 400", async () => {
    const manager = getProviderManager();
    (manager as any).claudeKey = "";
    const handler = getHandler(router, "/select", "post");
    const { req, res } = createMockReqRes({ body: { provider: "claude", apiKey: "" } });
    await handler(req, res);

    expect(res.statusCode).toBe(400);
    expect(res.body.error.toLowerCase()).toContain("not configured");
  });

  it("POST /api/v1/provider/select with unreachable Ollama returns 503", async () => {
    const handler = getHandler(router, "/select", "post");
    const { req, res } = createMockReqRes({
      body: { provider: "ollama", baseUrl: "http://127.0.0.1:59999", model: "nonexistent" },
    });
    await handler(req, res);

    expect(res.statusCode).toBe(503);
    expect(res.body.error).toContain("Ollama connection check failed");
  });
});
