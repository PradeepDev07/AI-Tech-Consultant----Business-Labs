export interface BaseModelProvider {
  readonly providerName: string;
  generateResponse(prompt: string, systemPrompt?: string): Promise<string>;
  checkHealth?(): Promise<{ status: string; latency_ms?: number; message?: string; provider: string; model?: string }>;
}

export class MockModelProvider implements BaseModelProvider {
  readonly providerName = "mock-inbox-model";

  async checkHealth(): Promise<{ status: string; latency_ms?: number; message?: string; provider: string }> {
    return {
      status: "ok",
      provider: this.providerName,
      message: "Mock model provider is ready (deterministic offline mode).",
    };
  }

  async generateResponse(prompt: string, _systemPrompt = ""): Promise<string> {
    const lowerPrompt = prompt.toLowerCase();

    // 1. Prompt Injection Guardrail
    if (
      lowerPrompt.includes("ignore previous instructions") ||
      lowerPrompt.includes("disregard all prior instructions") ||
      lowerPrompt.includes("system override") ||
      lowerPrompt.includes("reveal system prompt")
    ) {
      return JSON.stringify({
        primaryCategory: "security_sensitive_requests",
        detectedIntents: ["prompt_injection_attempt"],
        riskLevel: "high",
        requiresHumanReview: true,
        reason: "Adversarial prompt injection pattern detected in message text.",
      });
    }

    // 2. Classification JSON prompt
    if (
      lowerPrompt.includes("classify the following customer email") ||
      lowerPrompt.includes("json format:")
    ) {
      return this.classifyEmailText(prompt);
    }

    // 3. Draft Generation prompt
    return this.generateDraftText(prompt);
  }

  private classifyEmailText(prompt: string): string {
    // Extract only the email subject and body after "Subject: "
    const subjectIndex = prompt.indexOf("Subject: ");
    const text =
      subjectIndex !== -1 ? prompt.substring(subjectIndex).toLowerCase() : prompt.toLowerCase();

    const detectedIntents: string[] = [];
    let riskLevel: "low" | "medium" | "high" = "low";
    let requiresHumanReview = false;
    let reason = "Standard inquiry matching documented capabilities.";

    // Pre-detection flags based strictly on the email content
    const isInjection =
      text.includes("ignore previous instructions") ||
      text.includes("disregard all prior instructions") ||
      text.includes("system override") ||
      text.includes("reveal system prompt");

    const isSecurity =
      text.includes("sql injection") ||
      text.includes("vulnerability") ||
      text.includes("credential stuffing") ||
      text.includes("hipaa") ||
      text.includes("soc2") ||
      text.includes("rotate") ||
      text.includes("secret key") ||
      text.includes("unauthorized access") ||
      text.includes("pentest");

    const isPlanChange =
      text.includes("change plan") ||
      text.includes("upgrade my account") ||
      text.includes("transfer") ||
      text.includes("downgrade") ||
      text.includes("revoke") ||
      text.includes("gdpr") ||
      text.includes("erasure") ||
      text.includes("delete our directory") ||
      text.includes("ownership") ||
      text.includes("cancel subscription");

    const isBilling =
      text.includes("double charge") ||
      text.includes("refund") ||
      text.includes("invoice") ||
      text.includes("payment failed") ||
      text.includes("dispute") ||
      text.includes("chargeback") ||
      text.includes("card ending in") ||
      text.includes("w-9");

    const isAccess =
      text.includes("locked out") ||
      text.includes("ip blocked") ||
      text.includes("ip address has been temporarily blocked") ||
      text.includes("forgot password") ||
      text.includes("cannot receive password reset") ||
      text.includes("lost 2fa") ||
      text.includes("authenticator") ||
      text.includes("mysql root password") ||
      text.includes("sftp") ||
      text.includes("cpanel credentials") ||
      text.includes("admin login") ||
      text.includes("unblock me");

    const isComplaint =
      text.includes("unacceptable") ||
      text.includes("downtime") ||
      text.includes("ignored for") ||
      text.includes("disgraceful") ||
      text.includes("demand an explanation") ||
      text.includes("terrible service") ||
      text.includes("frustrated");

    const isTechSupport =
      text.includes("500 internal server error") ||
      text.includes("ssl certificate error") ||
      text.includes("privacy warning") ||
      text.includes("import wizard stops") ||
      text.includes("csv member import failing") ||
      text.includes("webhooks failing") ||
      text.includes("slow page load") ||
      text.includes("javascript library loading conflict") ||
      text.includes("typeerror") ||
      text.includes("bug in form builder");

    const isPricing =
      text.includes("pricing") ||
      text.includes("cost") ||
      text.includes("discount") ||
      text.includes("how much") ||
      text.includes("annual plan") ||
      text.includes("monthly plan") ||
      text.includes("lifetime license") ||
      text.includes("non-profit discount") ||
      text.includes("vat invoice");

    const isFeature =
      text.includes("how to") ||
      text.includes("how do i") ||
      text.includes("google maps") ||
      text.includes("custom form fields") ||
      text.includes("recurring automated member billing") ||
      text.includes("custom domain") ||
      text.includes("claim listings") ||
      text.includes("lead matching") ||
      text.includes("star ratings") ||
      text.includes("exporting directory members") ||
      text.includes("category hierarchy") ||
      text.includes("welcome email") ||
      text.includes("stripe");

    const isAmbiguous =
      text.includes("it is not working") ||
      text.includes("what i asked yesterday") ||
      text.includes("testing 123") ||
      (text.length < 40 && !isPricing && !isFeature);

    // Intent building
    if (isInjection) {
      detectedIntents.push("prompt_injection_attempt");
    }
    if (isPlanChange) {
      detectedIntents.push("account_or_permission_changes");
    }
    if (isBilling) {
      detectedIntents.push("billing_and_payment_issues");
    }
    if (isSecurity) {
      detectedIntents.push("security_sensitive_requests");
    }
    if (isAccess) {
      detectedIntents.push("directory_or_account_access");
    }
    if (isComplaint) {
      detectedIntents.push("complaints");
    }
    if (isTechSupport) {
      detectedIntents.push("technical_support");
    }
    if (isPricing) {
      detectedIntents.push("pricing_and_plans");
    }
    if (isFeature) {
      detectedIntents.push("standard_feature_questions");
    }
    if (isAmbiguous && detectedIntents.length === 0) {
      detectedIntents.push("unknown_or_ambiguous");
    }

    if (detectedIntents.length === 0) {
      detectedIntents.push("unknown_or_ambiguous");
    }

    // Determine primary category and risk
    let primaryCategory = detectedIntents[0];

    // Priority ordering for primary category
    if (isInjection || isSecurity) {
      primaryCategory = "security_sensitive_requests";
      riskLevel = "high";
      requiresHumanReview = true;
      reason = "Security-related inquiry or malicious pattern detected.";
    } else if (isBilling) {
      primaryCategory = "billing_and_payment_issues";
      riskLevel = "high";
      requiresHumanReview = true;
      reason = "Financial transaction or billing inquiry requires verified review.";
    } else if (isPlanChange) {
      primaryCategory = "account_or_permission_changes";
      riskLevel = "high";
      requiresHumanReview = true;
      reason = "Account modification or subscription plan changes require staff authorization.";
    } else if (isAccess) {
      primaryCategory = "directory_or_account_access";
      riskLevel = "high";
      requiresHumanReview = true;
      reason = "Account login, lockout, or credential inquiry.";
    } else if (isComplaint) {
      primaryCategory = "complaints";
      riskLevel = "high";
      requiresHumanReview = true;
      reason = "Customer complaint requires managerial attention.";
    } else if (isTechSupport) {
      primaryCategory = "technical_support";
      riskLevel = "medium";
      requiresHumanReview = true;
      reason = "Technical bug or error investigation required.";
    } else if (isPricing) {
      primaryCategory = "pricing_and_plans";
      riskLevel = "low";
      requiresHumanReview = false;
      reason = "Standard pricing inquiry.";
    } else if (isFeature) {
      primaryCategory = "standard_feature_questions";
      riskLevel = "low";
      requiresHumanReview = false;
      reason = "Standard feature documentation question.";
    } else {
      primaryCategory = "unknown_or_ambiguous";
      riskLevel = "medium";
      requiresHumanReview = true;
      reason = "Inquiry is vague or unclassified.";
    }

    return JSON.stringify({
      primaryCategory,
      detectedIntents,
      riskLevel,
      requiresHumanReview,
      reason,
    });
  }

  private generateDraftText(prompt: string): string {
    const lowerPrompt = prompt.toLowerCase();

    // Check if evidence is missing or abstained
    if (
      lowerPrompt.includes("[no relevant documentation found]") ||
      lowerPrompt.includes("abstained: true") ||
      lowerPrompt.includes("insufficient evidence")
    ) {
      return (
        "Dear Customer,\n\n" +
        "Thank you for contacting Brilliant Directories Support. We have forwarded your specific request to our technical team for review. A support specialist will follow up with you shortly with further information.\n\n" +
        "Best regards,\nBrilliant Directories Support Team"
      );
    }

    // Extract knowledge text if present
    let answerSnippet =
      "Here is the information from our Solution Center documentation regarding your inquiry.";
    const knowledgeMarker = "Task 1 Verified Knowledge:\n";
    const citationsMarker = "Authoritative Citations:\n";
    const kIdx = prompt.indexOf(knowledgeMarker);
    const cIdx = prompt.indexOf(citationsMarker);

    if (kIdx !== -1 && cIdx !== -1) {
      answerSnippet = prompt.substring(kIdx + knowledgeMarker.length, cIdx).trim();
    }

    // Extract URLs from citations
    const urlMatches = prompt.match(/https?:\/\/[^\s\)\],]+/g) || [];
    const uniqueUrls = Array.from(new Set(urlMatches)).filter(
      (u) => !u.includes("example.com") && !u.includes("localhost")
    );

    const citationsText =
      uniqueUrls.length > 0
        ? `\n\nFor more details, please visit the official documentation:\n${uniqueUrls.map((u) => `- ${u}`).join("\n")}`
        : "";

    return (
      `Dear Customer,\n\n` +
      `Thank you for contacting Brilliant Directories Support.\n\n` +
      `${answerSnippet}` +
      `${citationsText}\n\n` +
      `Please let us know if you have any questions.\n\n` +
      `Best regards,\n` +
      `Brilliant Directories Support Team`
    );
  }
}

export class OllamaModelProvider implements BaseModelProvider {
  readonly providerName: string;
  private readonly baseUrl: string;
  private readonly modelName: string;
  private resolvedModel: string | null = null;
  public lastTelemetry: Record<string, any> = {};

  constructor(baseUrl = "http://localhost:11434", modelName = "llama3.2:latest") {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.modelName = modelName;
    this.providerName = `ollama:${modelName}`;
  }

  async resolveModelTag(): Promise<string> {
    if (this.resolvedModel) {
      return this.resolvedModel;
    }
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 2000);
      const res = await fetch(`${this.baseUrl}/api/tags`, { signal: controller.signal });
      clearTimeout(timer);
      if (res.ok) {
        const data = (await res.json()) as any;
        const models: string[] = (data?.models || []).map((m: any) => m.name || m.model || "");
        if (models.includes(this.modelName)) {
          this.resolvedModel = this.modelName;
          return this.modelName;
        }
        const candidates = [
          `${this.modelName}-cloud`,
          `${this.modelName}:cloud`,
          `${this.modelName}:latest`,
        ];
        for (const cand of candidates) {
          if (models.includes(cand)) {
            this.resolvedModel = cand;
            return cand;
          }
        }
        for (const m of models) {
          if (m.startsWith(this.modelName) || m.includes(this.modelName)) {
            this.resolvedModel = m;
            return m;
          }
        }
      }
    } catch {
      // ignore
    }
    this.resolvedModel = this.modelName;
    return this.modelName;
  }

  async checkHealth(): Promise<{ status: string; latency_ms?: number; message?: string; provider: string; model?: string; resolved_model?: string }> {
    const t0 = Date.now();
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 2000);
      const res = await fetch(`${this.baseUrl}/api/tags`, { signal: controller.signal });
      clearTimeout(timer);
      const latency = Date.now() - t0;
      if (res.ok) {
        const data = (await res.json()) as any;
        const models = (data?.models || []).map((m: any) => m.name || m.model || "");
        const resolved = await this.resolveModelTag();
        const modelFound = models.includes(resolved) || models.some((m: string) => m.toLowerCase().includes(this.modelName.toLowerCase()));
        return {
          status: modelFound ? "ok" : "warning",
          provider: this.providerName,
          model: this.modelName,
          resolved_model: resolved,
          latency_ms: latency,
          message: modelFound
            ? `Connected to Ollama daemon. Model '${resolved}' is available.`
            : `Connected to Ollama, but model '${this.modelName}' not found in installed models: ${models.join(", ")}`,
        };
      }
      return {
        status: "error",
        provider: this.providerName,
        latency_ms: latency,
        message: `Ollama daemon returned HTTP ${res.status}`,
      };
    } catch (err: any) {
      return {
        status: "error",
        provider: this.providerName,
        latency_ms: Date.now() - t0,
        message: `Cannot connect to Ollama daemon at ${this.baseUrl}: ${err.message || err}`,
      };
    }
  }

  async generateResponse(prompt: string, systemPrompt = ""): Promise<string> {
    const actualModel = await this.resolveModelTag();
    const url = `${this.baseUrl}/api/chat`;
    const payload = {
      model: actualModel,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: prompt },
      ],
      stream: false,
      options: { temperature: 0.1 },
    };

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(60000),
    });

    if (!res.ok) {
      const err = await res.text().catch(() => "");
      throw new Error(`Ollama model error HTTP ${res.status}: ${err}`);
    }

    const data = (await res.json()) as any;
    this.lastTelemetry = {
      model: data?.model || actualModel,
      prompt_eval_count: data?.prompt_eval_count || 0,
      prompt_eval_cached_count: data?.prompt_eval_cached_count || 0,
      eval_count: data?.eval_count || 0,
      total_duration_ms: data?.total_duration ? Math.round(data.total_duration / 1000000) : 0,
    };

    const content = data?.message?.content?.trim();
    if (content) return content;
    if (data?.message?.thinking) return data.message.thinking.trim();
    return "";
  }
}

export class ClaudeModelProvider implements BaseModelProvider {
  readonly providerName: string;
  private readonly apiKey: string;
  private readonly modelName: string;
  private readonly timeoutMs: number;

  constructor(apiKey?: string, modelName = "claude-3-5-sonnet-20241022", timeoutMs = 30000) {
    this.apiKey = apiKey || process.env.ANTHROPIC_API_KEY || "";
    this.modelName = modelName;
    this.timeoutMs = timeoutMs;
    this.providerName = `claude:${this.modelName}`;
  }

  async checkHealth(): Promise<{ status: string; latency_ms?: number; message?: string; provider: string; model?: string }> {
    if (!this.apiKey) {
      return {
        status: "error",
        provider: this.providerName,
        message: "Anthropic API key is not configured. Set ANTHROPIC_API_KEY on the server or in the dashboard.",
      };
    }

    const t0 = Date.now();
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 8000);
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "x-api-key": this.apiKey,
          "anthropic-version": "2023-06-01",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          model: this.modelName,
          max_tokens: 10,
          messages: [{ role: "user", content: "ping" }],
        }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      const latency = Date.now() - t0;

      if (res.status === 200) {
        return {
          status: "ok",
          provider: this.providerName,
          model: this.modelName,
          latency_ms: latency,
          message: `Connected to Anthropic Claude (${this.modelName}).`,
        };
      } else if (res.status === 401) {
        return {
          status: "error",
          provider: this.providerName,
          latency_ms: latency,
          message: "Authentication failed: Invalid Anthropic API Key.",
        };
      } else if (res.status === 429) {
        return {
          status: "warning",
          provider: this.providerName,
          latency_ms: latency,
          message: "Anthropic Claude rate limit reached (HTTP 429).",
        };
      } else {
        const text = await res.text().catch(() => "");
        return {
          status: "error",
          provider: this.providerName,
          latency_ms: latency,
          message: `Anthropic API returned HTTP ${res.status}: ${text.substring(0, 120)}`,
        };
      }
    } catch (err: any) {
      return {
        status: "error",
        provider: this.providerName,
        latency_ms: Date.now() - t0,
        message: `Network error connecting to Anthropic Claude API: ${err.message || err}`,
      };
    }
  }

  async generateResponse(prompt: string, systemPrompt = ""): Promise<string> {
    if (!this.apiKey) {
      throw new Error("Anthropic API key is not configured. Set ANTHROPIC_API_KEY.");
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "x-api-key": this.apiKey,
          "anthropic-version": "2023-06-01",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          model: this.modelName,
          max_tokens: 1024,
          system: systemPrompt,
          messages: [{ role: "user", content: prompt }],
          temperature: 0.0,
        }),
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (!res.ok) {
        const errText = await res.text().catch(() => "");
        throw new Error(`Anthropic Claude API returned HTTP ${res.status}: ${errText.substring(0, 150)}`);
      }

      const data = (await res.json()) as any;
      const contentBlocks = data?.content || [];
      const textBlocks = contentBlocks
        .filter((b: any) => b.type === "text")
        .map((b: any) => b.text || "");

      return textBlocks.join("\n").trim();
    } catch (err: any) {
      clearTimeout(timer);
      throw new Error(`Failed to communicate with Claude API: ${err.message || err}`);
    }
  }
}

export class ProviderManager {
  private providerType: string = "mock";
  private ollamaUrl: string = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
  private ollamaModel: string = process.env.CHAT_MODEL || process.env.MODEL_NAME || "smollm:135m";
  private claudeKey: string = process.env.ANTHROPIC_API_KEY || "";
  private claudeModel: string = process.env.CLAUDE_MODEL || "claude-3-5-sonnet-20241022";
  private activeProvider: BaseModelProvider = new MockModelProvider();

  constructor() {
    this.initActiveFromEnv();
  }

  private initActiveFromEnv(): void {
    const envProvider = (process.env.MODEL_PROVIDER || "mock").toLowerCase().trim();
    if (envProvider === "ollama") {
      this.providerType = "ollama";
      this.activeProvider = new OllamaModelProvider(this.ollamaUrl, this.ollamaModel);
    } else if (envProvider === "claude" && this.claudeKey) {
      this.providerType = "claude";
      this.activeProvider = new ClaudeModelProvider(this.claudeKey, this.claudeModel);
    }
  }

  getActiveProvider(): BaseModelProvider {
    return this.activeProvider;
  }

  async getStatus(): Promise<Record<string, any>> {
    let ollamaModels: string[] = [];
    let ollamaReachable = false;
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 1500);
      const res = await fetch(`${this.ollamaUrl}/api/tags`, { signal: controller.signal });
      clearTimeout(timer);
      if (res.ok) {
        ollamaReachable = true;
        const data = (await res.json()) as any;
        ollamaModels = (data.models || []).map((m: any) => m.name || m.model || "");
      }
    } catch {
      // ignore
    }

    return {
      active_provider_type: this.providerType,
      active_provider_name: this.activeProvider.providerName,
      available_providers: ["mock", "ollama", "claude"],
      claude: {
        configured: Boolean(this.claudeKey),
        model: this.claudeModel,
      },
      ollama: {
        base_url: this.ollamaUrl,
        model: this.ollamaModel,
        reachable: ollamaReachable,
        installed_models: ollamaModels,
      },
      mock: {
        model: "mock-inbox-model",
        ready: true,
      },
    };
  }

  async setActiveProvider(
    providerType: string,
    options: { model?: string; apiKey?: string; baseUrl?: string } = {}
  ): Promise<{ success: boolean; active_provider: string; health?: any }> {
    const norm = providerType.trim().toLowerCase();
    if (!["mock", "ollama", "claude"].includes(norm)) {
      throw new Error(`Invalid provider '${providerType}'. Must be 'mock', 'ollama', or 'claude'.`);
    }

    if (norm === "mock") {
      this.providerType = "mock";
      this.activeProvider = new MockModelProvider();
      return { success: true, active_provider: this.activeProvider.providerName };
    }

    if (norm === "ollama") {
      if (options.baseUrl) this.ollamaUrl = options.baseUrl.replace(/\/+$/, "");
      if (options.model) this.ollamaModel = options.model.trim();
      const provider = new OllamaModelProvider(this.ollamaUrl, this.ollamaModel);
      const health = await provider.checkHealth();
      if (health.status === "error") {
        throw new Error(`Ollama connection check failed: ${health.message}`);
      }
      this.providerType = "ollama";
      this.activeProvider = provider;
      return { success: true, active_provider: this.activeProvider.providerName, health };
    }

    if (norm === "claude") {
      if (options.apiKey) this.claudeKey = options.apiKey.trim();
      if (options.model) this.claudeModel = options.model.trim();
      if (!this.claudeKey) {
        throw new Error("Cannot select Claude: Anthropic API key is not configured.");
      }
      const provider = new ClaudeModelProvider(this.claudeKey, this.claudeModel);
      this.providerType = "claude";
      this.activeProvider = provider;
      return { success: true, active_provider: this.activeProvider.providerName };
    }

    throw new Error(`Unhandled provider '${norm}'`);
  }

  async testProvider(
    providerType: string,
    options: { model?: string; apiKey?: string; baseUrl?: string } = {}
  ): Promise<any> {
    const norm = providerType.trim().toLowerCase();
    if (norm === "mock") {
      return new MockModelProvider().checkHealth();
    }
    if (norm === "ollama") {
      const url = options.baseUrl ? options.baseUrl.replace(/\/+$/, "") : this.ollamaUrl;
      const model = options.model ? options.model.trim() : this.ollamaModel;
      return new OllamaModelProvider(url, model).checkHealth();
    }
    if (norm === "claude") {
      const key = options.apiKey ? options.apiKey.trim() : this.claudeKey;
      const model = options.model ? options.model.trim() : this.claudeModel;
      return new ClaudeModelProvider(key, model).checkHealth();
    }
    return { status: "error", message: `Unknown provider '${providerType}'.` };
  }
}

const globalProviderManager = new ProviderManager();

export function getProviderManager(): ProviderManager {
  return globalProviderManager;
}
