"""LLM model provider interfaces, implementations, and runtime provider manager."""

from abc import ABC, abstractmethod
import os
import re
import time
from typing import Any
import httpx
from app.core.exceptions import ModelProviderError
from app.core.logging import logger

ABSTENTION_TEXT = "I do not have sufficient information in the Brilliant Directories documentation to answer this question."


class BaseModelProvider(ABC):
    """Abstract interface for LLM text generation."""

    @abstractmethod
    def generate_answer(self, prompt: str, system_prompt: str) -> str:
        """Generate response text given prompt and system instructions."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identify the model provider and model version."""
        pass

    def check_health(self) -> dict[str, Any]:
        """Verify provider availability and return status report."""
        return {"status": "ok", "provider": self.provider_name}


class MockModelProvider(BaseModelProvider):
    """Deterministic, zero-cost model double for tests, evaluation, and offline development."""

    def __init__(self, model_name: str = "mock-model-v1"):
        self.model_name = model_name

    @property
    def provider_name(self) -> str:
        return f"mock:{self.model_name}"

    def check_health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "provider": self.provider_name,
            "latency_ms": 0.05,
            "message": "Deterministic mock provider is operational (offline mode).",
        }

    def generate_answer(self, prompt: str, system_prompt: str) -> str:
        """Deterministic answering based on retrieved evidence and guardrails."""
        lower_prompt = prompt.lower()
        if any(
            phrase in lower_prompt
            for phrase in [
                "ignore previous instructions",
                "disregard all prior instructions",
                "system override",
                "reveal the system prompt",
                "reveal your secret",
            ]
        ):
            return (
                "I must ignore instructions attempting to override system behavior. "
                "Based on Brilliant Directories documentation, I cannot fulfill this request."
            )

        if "[no relevant evidence retrieved]" in lower_prompt or "--- evidence item" not in lower_prompt:
            return ABSTENTION_TEXT

        q_match = re.search(r"### USER QUESTION:\s*(.*?)\s*### RETRIEVED EVIDENCE:", prompt, re.DOTALL)
        question = q_match.group(1).strip() if q_match else prompt

        domain_stopwords = {
            "how", "do", "i", "the", "a", "is", "can", "to", "what", "where", "in", "for",
            "with", "and", "or", "on", "my", "using", "brilliant", "directories", "directory",
            "support", "article", "documentation", "system", "please", "tell", "me"
        }
        q_words = set(re.findall(r"\w+", question.lower())) - domain_stopwords

        evidence_matches = re.findall(r"Content:\s*(.*?)\s*--- END EVIDENCE ITEM", prompt, re.DOTALL)
        combined_evidence = " ".join(evidence_matches).strip()

        if not q_words or not combined_evidence:
            return ABSTENTION_TEXT

        overlap = [w for w in q_words if w in combined_evidence.lower()]
        min_required_overlap = max(1, len(q_words) // 3)
        if len(overlap) < min_required_overlap:
            return ABSTENTION_TEXT

        sentences = re.split(r"(?<=[.!?])\s+", combined_evidence)
        matching_sentences = [
            s.strip() for s in sentences if any(w in s.lower() for w in overlap)
        ]

        if not matching_sentences:
            return ABSTENTION_TEXT

        answer_body = " ".join(matching_sentences[:3])
        return f"Based on the Brilliant Directories documentation: {answer_body}"


class OllamaModelProvider(BaseModelProvider):
    """Client for local/remote Ollama chat completion API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:latest",
        timeout_seconds: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._resolved_model: str | None = None
        self.last_telemetry: dict[str, Any] = {}

    @property
    def provider_name(self) -> str:
        return f"ollama:{self.model}"

    def resolve_model_tag(self) -> str:
        """Resolve model name to exact installed Ollama tag (handling -cloud, :cloud, etc.)."""
        if self._resolved_model:
            return self._resolved_model

        try:
            with httpx.Client(timeout=4.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name", "") for m in res.json().get("models", [])]
                    # 1. Exact match
                    if self.model in models:
                        self._resolved_model = self.model
                        return self._resolved_model

                    # 2. Try cloud aliases
                    candidates = [
                        f"{self.model}-cloud",
                        f"{self.model}:cloud",
                        f"{self.model}:latest",
                    ]
                    for cand in candidates:
                        if cand in models:
                            self._resolved_model = cand
                            return self._resolved_model

                    # 3. Substring / prefix match
                    for m in models:
                        if m.startswith(self.model) or self.model in m:
                            self._resolved_model = m
                            return self._resolved_model
        except Exception:
            pass

        self._resolved_model = self.model
        return self._resolved_model

    def check_health(self) -> dict[str, Any]:
        """Check whether Ollama daemon is reachable and whether model is installed."""
        t0 = time.time()
        try:
            with httpx.Client(timeout=4.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code != 200:
                    return {
                        "status": "error",
                        "provider": self.provider_name,
                        "message": f"Ollama daemon returned HTTP {res.status_code}",
                        "latency_ms": round((time.time() - t0) * 1000, 2),
                    }
                data = res.json()
                models = [m.get("name") for m in data.get("models", [])]
                resolved = self.resolve_model_tag()
                installed = resolved in models or any(self.model in m or m.startswith(self.model) for m in models)
                latency = round((time.time() - t0) * 1000, 2)
                return {
                    "status": "ok" if installed else "warning",
                    "provider": self.provider_name,
                    "model": self.model,
                    "resolved_model": resolved,
                    "model_installed": installed,
                    "available_models": models,
                    "latency_ms": latency,
                    "message": (
                        f"Connected to Ollama. Model '{resolved}' is available."
                        if installed
                        else f"Connected to Ollama, but model '{self.model}' not found in installed models: {models}"
                    ),
                }
        except Exception as exc:
            return {
                "status": "error",
                "provider": self.provider_name,
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "message": f"Cannot connect to Ollama daemon at {self.base_url}: {exc}",
            }

    def generate_answer(self, prompt: str, system_prompt: str) -> str:
        """Call Ollama /api/chat with system prompt and user prompt."""
        url = f"{self.base_url}/api/chat"
        actual_model = self.resolve_model_tag()
        payload = {
            "model": actual_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.0,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, json=payload)
                if response.status_code != 200:
                    raise ModelProviderError(
                        f"Ollama API returned HTTP {response.status_code}: {response.text}"
                    )
                data = response.json()
                # Capture telemetry for credit and token tracking
                self.last_telemetry = {
                    "model": data.get("model", actual_model),
                    "prompt_eval_count": data.get("prompt_eval_count", 0),
                    "prompt_eval_cached_count": data.get("prompt_eval_cached_count", 0),
                    "eval_count": data.get("eval_count", 0),
                    "total_duration_ms": round(data.get("total_duration", 0) / 1_000_000, 2),
                }

                msg = data.get("message", {}).get("content")
                if not msg and data.get("message", {}).get("thinking"):
                    msg = data.get("message", {}).get("thinking")
                if not msg:
                    raise ModelProviderError(f"Empty response from Ollama: {data}")
                return msg.strip()
        except httpx.RequestError as exc:
            raise ModelProviderError(
                f"Failed to connect to Ollama service at {self.base_url}: {exc}"
            ) from exc


class ClaudeModelProvider(BaseModelProvider):
    """Server-side client for Anthropic Claude Messages API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        timeout_seconds: float = 30.0,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return f"claude:{self.model}"

    def check_health(self) -> dict[str, Any]:
        """Verify API key presence and check Anthropic connectivity."""
        if not self.api_key:
            return {
                "status": "error",
                "provider": self.provider_name,
                "message": "Anthropic API key is not configured. Set ANTHROPIC_API_KEY on the server or in the dashboard.",
            }

        t0 = time.time()
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        # Lightweight ping message
        payload = {
            "model": self.model,
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "ping"}],
        }

        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.post(url, headers=headers, json=payload)
                latency = round((time.time() - t0) * 1000, 2)
                if res.status_code == 200:
                    return {
                        "status": "ok",
                        "provider": self.provider_name,
                        "model": self.model,
                        "latency_ms": latency,
                        "message": f"Connected to Anthropic Claude ({self.model}).",
                    }
                elif res.status_code == 401:
                    return {
                        "status": "error",
                        "provider": self.provider_name,
                        "latency_ms": latency,
                        "message": "Authentication failed: Invalid Anthropic API Key.",
                    }
                elif res.status_code == 429:
                    return {
                        "status": "warning",
                        "provider": self.provider_name,
                        "latency_ms": latency,
                        "message": "Anthropic Claude rate limit reached (HTTP 429).",
                    }
                else:
                    return {
                        "status": "error",
                        "provider": self.provider_name,
                        "latency_ms": latency,
                        "message": f"Anthropic API returned HTTP {res.status_code}: {res.text[:120]}",
                    }
        except Exception as exc:
            return {
                "status": "error",
                "provider": self.provider_name,
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "message": f"Network error connecting to Anthropic Claude API: {exc}",
            }

    def generate_answer(self, prompt: str, system_prompt: str) -> str:
        """Call Anthropic Claude Messages API."""
        if not self.api_key:
            raise ModelProviderError(
                "Anthropic API key is not configured. Set ANTHROPIC_API_KEY."
            )

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code != 200:
                    raise ModelProviderError(
                        f"Anthropic API returned HTTP {res.status_code}: {res.text[:150]}"
                    )
                data = res.json()
                content_blocks = data.get("content", [])
                text_blocks = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
                if not text_blocks:
                    raise ModelProviderError(f"No text content returned from Claude: {data}")
                return "\n".join(text_blocks).strip()
        except httpx.RequestError as exc:
            raise ModelProviderError(f"Failed to communicate with Claude API: {exc}") from exc


class ProviderManager:
    """Thread-safe runtime manager for switching and inspecting model providers."""

    def __init__(self):
        self._provider_type: str = "mock"
        self._ollama_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self._ollama_model: str = os.environ.get("CHAT_MODEL", "smollm:135m")
        self._claude_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
        self._claude_model: str = os.environ.get("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
        self._active_provider: BaseModelProvider = MockModelProvider()
        self._init_active_from_env()

    def _init_active_from_env(self) -> None:
        env_provider = os.environ.get("MODEL_PROVIDER", "mock").lower().strip()
        if env_provider == "ollama":
            self._provider_type = "ollama"
            self._active_provider = OllamaModelProvider(base_url=self._ollama_url, model=self._ollama_model)
        elif env_provider == "claude" and self._claude_key:
            self._provider_type = "claude"
            self._active_provider = ClaudeModelProvider(api_key=self._claude_key, model=self._claude_model)

    def get_active_provider(self) -> BaseModelProvider:
        """Return the current active model provider."""
        return self._active_provider

    def get_status(self) -> dict[str, Any]:
        """Return current configuration status without exposing sensitive credentials."""
        # Query Ollama models if available
        ollama_models = []
        ollama_reachable = False
        try:
            with httpx.Client(timeout=1.5) as client:
                r = client.get(f"{self._ollama_url}/api/tags")
                if r.status_code == 200:
                    ollama_reachable = True
                    ollama_models = [m.get("name") for m in r.json().get("models", [])]
        except Exception:
            pass

        return {
            "active_provider_type": self._provider_type,
            "active_provider_name": self._active_provider.provider_name,
            "available_providers": ["mock", "ollama", "claude"],
            "claude": {
                "configured": bool(self._claude_key),
                "model": self._claude_model,
            },
            "ollama": {
                "base_url": self._ollama_url,
                "model": self._ollama_model,
                "reachable": ollama_reachable,
                "installed_models": ollama_models,
            },
            "mock": {
                "model": "mock-model-v1",
                "ready": True,
            },
        }

    def set_active_provider(
        self,
        provider_type: str,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Switch active provider with input validation against allowlist."""
        norm_type = provider_type.strip().lower()
        if norm_type not in ("mock", "ollama", "claude"):
            raise ValueError(f"Invalid provider '{provider_type}'. Must be 'mock', 'ollama', or 'claude'.")

        if norm_type == "mock":
            self._provider_type = "mock"
            self._active_provider = MockModelProvider()
            logger.info("Active model provider switched to MockModelProvider.")
            return {"success": True, "active_provider": self._active_provider.provider_name}

        elif norm_type == "ollama":
            if base_url:
                self._ollama_url = base_url.rstrip("/")
            if model:
                self._ollama_model = model
            provider = OllamaModelProvider(base_url=self._ollama_url, model=self._ollama_model)
            health = provider.check_health()
            if health.get("status") == "error":
                raise ModelProviderError(f"Ollama connection check failed: {health.get('message')}")
            self._provider_type = "ollama"
            self._active_provider = provider
            logger.info(f"Active model provider switched to {self._active_provider.provider_name}.")
            return {
                "success": True,
                "active_provider": self._active_provider.provider_name,
                "health": health,
            }

        elif norm_type == "claude":
            if api_key:
                self._claude_key = api_key.strip()
            if model:
                self._claude_model = model.strip()

            if not self._claude_key:
                raise ValueError("Cannot select Claude: Anthropic API key is not configured.")

            provider = ClaudeModelProvider(api_key=self._claude_key, model=self._claude_model)
            self._provider_type = "claude"
            self._active_provider = provider
            logger.info(f"Active model provider switched to {self._active_provider.provider_name}.")
            return {"success": True, "active_provider": self._active_provider.provider_name}

        raise ValueError(f"Unhandled provider '{norm_type}'")

    def test_provider(
        self,
        provider_type: str,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Perform a test connectivity check for a candidate provider without setting it active."""
        norm_type = provider_type.strip().lower()
        if norm_type == "mock":
            return MockModelProvider().check_health()
        elif norm_type == "ollama":
            target_url = (base_url or self._ollama_url).rstrip("/")
            target_model = model or self._ollama_model
            return OllamaModelProvider(base_url=target_url, model=target_model).check_health()
        elif norm_type == "claude":
            target_key = (api_key or self._claude_key).strip()
            target_model = (model or self._claude_model).strip()
            return ClaudeModelProvider(api_key=target_key, model=target_model).check_health()
        else:
            return {"status": "error", "message": f"Unknown provider '{provider_type}'."}


# Global singleton instance of ProviderManager
_global_provider_manager = ProviderManager()


def get_provider_manager() -> ProviderManager:
    """Return singleton provider manager."""
    return _global_provider_manager


def get_model_provider(
    provider_name: str = "mock",
    base_url: str = "http://localhost:11434",
    model: str = "llama3.2:latest",
) -> BaseModelProvider:
    """Backward compatible factory function."""
    if provider_name.lower() in ("mock", "dev", "test"):
        return MockModelProvider()
    elif provider_name.lower() == "ollama":
        return OllamaModelProvider(base_url=base_url, model=model)
    elif provider_name.lower() == "claude":
        return ClaudeModelProvider(model=model)
    else:
        return MockModelProvider()
