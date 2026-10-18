"""Model provider interfaces and implementations for Task 3."""

import abc
import json
import logging
import os
import time
from typing import Any
import httpx

logger = logging.getLogger("meeting_to_scope.model_provider")


class BaseModelProvider(abc.ABC):
    """Abstract interface for LLM text and structured response generation."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""
        pass

    @abc.abstractmethod
    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Generate response text for a given prompt and system instructions."""
        pass

    def check_health(self) -> dict[str, Any]:
        """Verify connectivity and readiness of the provider."""
        return {"status": "ok", "provider": self.provider_name}


class MockModelProvider(BaseModelProvider):
    """Deterministic, zero-cost model provider for reproducible testing and evaluation."""

    def __init__(self, provider_name: str = "mock-scope-model"):
        self._provider_name = provider_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def check_health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "provider": self.provider_name,
            "message": "Mock model provider is ready (deterministic offline mode).",
        }

    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        lower_prompt = prompt.lower()

        # 1. Prompt Injection Trap
        if (
            "ignore previous instructions" in lower_prompt
            or "disregard all prior instructions" in lower_prompt
            or "system override" in lower_prompt
            or "reveal system prompt" in lower_prompt
        ):
            return json.dumps({
                "security_alert": "prompt_injection_detected",
                "message": "Adversarial instructions quarantined. Standard analysis applied.",
            })

        # 2. Requirements Extraction
        if "extract structured requirements" in lower_prompt or "requirements extraction" in lower_prompt:
            return self._mock_requirements(prompt)

        # 3. Estimation Breakdown
        if "estimate effort" in lower_prompt or "work package" in lower_prompt:
            return self._mock_estimates(prompt)

        # 4. Scope Diff
        if "compare the following scopes" in lower_prompt or "scope difference" in lower_prompt:
            return self._mock_diff(prompt)

        # Fallback
        return "Standard analysis completed based on verified transcript inputs."

    def _mock_requirements(self, prompt: str) -> str:
        return json.dumps({
            "requirements": [
                {
                    "id": "REQ-001",
                    "category": "functional",
                    "title": "Directory Member Directory Setup",
                    "description": "Configure member directory with location search and category filters.",
                    "source_quote": "We need a directory where members can search by city and category.",
                    "status": "confirmed",
                    "priority": "high",
                    "acceptance_criteria": ["Members can search by city", "Category dropdown filters results"],
                    "assumptions": ["Standard Brilliant Directories search widgets are used"],
                    "risks": [],
                    "dependencies": ["Google Maps API"],
                    "confidence_score": 1.0,
                }
            ]
        })

    def _mock_estimates(self, prompt: str) -> str:
        return json.dumps({
            "estimates": [
                {
                    "requirement_id": "REQ-001",
                    "task_description": "Configure search widgets and category hierarchy",
                    "hours_low": 8.0,
                    "hours_base": 14.0,
                    "hours_high": 20.0,
                    "confidence_range": "medium",
                    "assumptions": ["Core BD settings suffice without custom PHP"],
                    "risk_factors": ["Google Maps billing setup delay"],
                    "requires_validation": False,
                }
            ]
        })

    def _mock_diff(self, prompt: str) -> str:
        return json.dumps({
            "summary": "Detected scope modifications from subsequent discussion.",
            "changes": [
                {
                    "requirement_id": "REQ-002",
                    "change_type": "added",
                    "title": "Automated Member Lead Distribution",
                    "new_value": "Visitors can submit quote requests automatically dispatched to members.",
                    "reason_and_quote": "We also want visitors to submit quote requests that route to matching members.",
                    "effort_impact_hours": 16.0,
                    "risk_impact": "low",
                    "clarification_needed": False,
                }
            ]
        })


class OllamaModelProvider(BaseModelProvider):
    """Local or cloud Ollama model adapter."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "llama3.2:latest",
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self._resolved_model: str | None = None
        self.last_telemetry: dict[str, Any] = {}

    @property
    def provider_name(self) -> str:
        return f"ollama:{self.model_name}"

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
                    if self.model_name in models:
                        self._resolved_model = self.model_name
                        return self._resolved_model

                    # 2. Try cloud aliases
                    candidates = [
                        f"{self.model_name}-cloud",
                        f"{self.model_name}:cloud",
                        f"{self.model_name}:latest",
                    ]
                    for cand in candidates:
                        if cand in models:
                            self._resolved_model = cand
                            return self._resolved_model

                    # 3. Substring / prefix match
                    for m in models:
                        if m.startswith(self.model_name) or self.model_name in m:
                            self._resolved_model = m
                            return self._resolved_model
        except Exception:
            pass

        self._resolved_model = self.model_name
        return self._resolved_model

    def check_health(self) -> dict[str, Any]:
        t0 = time.time()
        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                latency = round((time.time() - t0) * 1000, 2)
                if resp.status_code == 200:
                    models = [m.get("name") for m in resp.json().get("models", [])]
                    resolved = self.resolve_model_tag()
                    model_found = resolved in models or any(self.model_name.lower() in m.lower() for m in models)
                    return {
                        "status": "ok" if model_found else "warning",
                        "provider": self.provider_name,
                        "model": self.model_name,
                        "resolved_model": resolved,
                        "latency_ms": latency,
                        "message": (
                            f"Connected to Ollama daemon. Model '{resolved}' is available."
                            if model_found
                            else f"Connected to Ollama, but model '{self.model_name}' not found in installed models: {models}"
                        ),
                    }
                return {
                    "status": "error",
                    "provider": self.provider_name,
                    "latency_ms": latency,
                    "message": f"Ollama daemon returned HTTP {resp.status_code}",
                }
        except Exception as exc:
            return {
                "status": "error",
                "provider": self.provider_name,
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "message": f"Cannot connect to Ollama daemon at {self.base_url}: {exc}",
            }

    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        actual_model = self.resolve_model_tag()
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": actual_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Ollama error HTTP {response.status_code}: {response.text}"
                )
            data = response.json()
            self.last_telemetry = {
                "model": data.get("model", actual_model),
                "prompt_eval_count": data.get("prompt_eval_count", 0),
                "prompt_eval_cached_count": data.get("prompt_eval_cached_count", 0),
                "eval_count": data.get("eval_count", 0),
                "total_duration_ms": round(data.get("total_duration", 0) / 1_000_000, 2),
            }
            msg = data.get("message", {}).get("content", "").strip()
            if not msg and data.get("message", {}).get("thinking"):
                msg = data.get("message", {}).get("thinking", "").strip()
            return msg


class ClaudeModelProvider(BaseModelProvider):
    """Server-side client for Anthropic Claude Messages API."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "claude-3-5-sonnet-20241022",
        timeout_seconds: float = 30.0,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return f"claude:{self.model_name}"

    def check_health(self) -> dict[str, Any]:
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
        payload = {
            "model": self.model_name,
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
                        "model": self.model_name,
                        "latency_ms": latency,
                        "message": f"Connected to Anthropic Claude ({self.model_name}).",
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

    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key:
            raise RuntimeError(
                "Anthropic API key is not configured. Set ANTHROPIC_API_KEY."
            )

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code != 200:
                raise RuntimeError(
                    f"Anthropic API returned HTTP {res.status_code}: {res.text[:150]}"
                )
            data = res.json()
            content_blocks = data.get("content", [])
            text_blocks = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            if not text_blocks:
                raise RuntimeError(f"No text content returned from Claude: {data}")
            return "\n".join(text_blocks).strip()


class ProviderManager:
    """Thread-safe runtime manager for switching and inspecting model providers in Task 3."""

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
            self._active_provider = OllamaModelProvider(base_url=self._ollama_url, model_name=self._ollama_model)
        elif env_provider == "claude" and self._claude_key:
            self._provider_type = "claude"
            self._active_provider = ClaudeModelProvider(api_key=self._claude_key, model_name=self._claude_model)

    def get_active_provider(self) -> BaseModelProvider:
        return self._active_provider

    def get_status(self) -> dict[str, Any]:
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
                "model": "mock-scope-model",
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
        norm_type = provider_type.strip().lower()
        if norm_type not in ("mock", "ollama", "claude"):
            raise ValueError(f"Invalid provider '{provider_type}'. Must be 'mock', 'ollama', or 'claude'.")

        if norm_type == "mock":
            self._provider_type = "mock"
            self._active_provider = MockModelProvider()
            logger.info("Task 3 active model provider switched to MockModelProvider.")
            return {"success": True, "active_provider": self._active_provider.provider_name}

        elif norm_type == "ollama":
            if base_url:
                self._ollama_url = base_url.rstrip("/")
            if model:
                self._ollama_model = model.strip()
            provider = OllamaModelProvider(base_url=self._ollama_url, model_name=self._ollama_model)
            health = provider.check_health()
            if health.get("status") == "error":
                raise RuntimeError(f"Ollama connection check failed: {health.get('message')}")
            self._provider_type = "ollama"
            self._active_provider = provider
            logger.info(f"Task 3 active model provider switched to {self._active_provider.provider_name}.")
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

            provider = ClaudeModelProvider(api_key=self._claude_key, model_name=self._claude_model)
            self._provider_type = "claude"
            self._active_provider = provider
            logger.info(f"Task 3 active model provider switched to {self._active_provider.provider_name}.")
            return {"success": True, "active_provider": self._active_provider.provider_name}

        raise ValueError(f"Unhandled provider '{norm_type}'")

    def test_provider(
        self,
        provider_type: str,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        norm_type = provider_type.strip().lower()
        if norm_type == "mock":
            return MockModelProvider().check_health()
        elif norm_type == "ollama":
            target_url = (base_url or self._ollama_url).rstrip("/")
            target_model = (model or self._ollama_model).strip()
            return OllamaModelProvider(base_url=target_url, model_name=target_model).check_health()
        elif norm_type == "claude":
            target_key = (api_key or self._claude_key).strip()
            target_model = (model or self._claude_model).strip()
            return ClaudeModelProvider(api_key=target_key, model_name=target_model).check_health()
        else:
            return {"status": "error", "message": f"Unknown provider '{provider_type}'."}


_global_provider_manager = ProviderManager()


def get_provider_manager() -> ProviderManager:
    return _global_provider_manager
