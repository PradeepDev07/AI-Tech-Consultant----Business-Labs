import { BaseModelProvider, getProviderManager } from "./model-provider.js";

export class DelegatingModelProvider implements BaseModelProvider {
  get providerName(): string {
    return getProviderManager().getActiveProvider().providerName;
  }

  generateResponse(prompt: string, systemPrompt?: string): Promise<string> {
    return getProviderManager().getActiveProvider().generateResponse(prompt, systemPrompt);
  }

  async checkHealth() {
    const active = getProviderManager().getActiveProvider();
    if (typeof active.checkHealth === "function") {
      return active.checkHealth();
    }
    return { status: "ok", provider: active.providerName };
  }
}

const delegatingProvider = new DelegatingModelProvider();

export function getConfiguredModelProvider(): BaseModelProvider {
  return delegatingProvider;
}
