"""LLM provider abstraction.

All our LLM backends speak the OpenAI-compatible chat API, so a provider only needs to
vary three things: the base URL, the auth/extra headers, and the model names. This keeps
the rest of the codebase backend-agnostic — callers ask the active provider for a URL and
headers instead of hard-coding OpenRouter specifics.

Switch backends with the LLM_PROVIDER env var ("openrouter" | "ollama"); per-provider
connection details live in their own settings fields (see config.py).
"""
from __future__ import annotations

from typing import Any


class LLMProvider:
    """An OpenAI-compatible chat backend: base URL, headers, and model names.

    Reads the *effective* connection (settings.llm_*), which config.model_post_init has
    already pointed at the selected backend — so subclasses differ only in headers().
    """

    name = "base"
    # OpenRouter routes :free models through a globally-shared pool that is rate-limited
    # upstream regardless of our pacing; task generation cools down before its (last,
    # largest) call only for such shared backends. Self-hosted/own-quota backends don't.
    shared_rate_limited = False

    def __init__(self, settings: Any) -> None:
        self.base_url: str = settings.llm_base_url
        self.api_key: str = settings.llm_api_key
        self.model: str = settings.llm_model
        self.fallback_model: str | None = settings.llm_fallback_model or None
        self.vision_model: str = getattr(settings, "llm_vision_model", "") or self.model
        self.vision_fallback_model: str | None = getattr(settings, "llm_vision_fallback_model", None) or None

    def chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def headers(self) -> dict[str, str]:
        raise NotImplementedError


class OpenRouterProvider(LLMProvider):
    name = "openrouter"
    shared_rate_limited = True

    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # OpenRouter attribution headers; ignored by other backends.
            "HTTP-Referer": "https://proof-forge.ru",
            "X-Title": "Grasp",
        }


class OllamaProvider(LLMProvider):
    name = "ollama"
    shared_rate_limited = False

    def headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        # Local Ollama ignores the key; Ollama Cloud requires it. Send it only when set.
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h


_PROVIDERS = {p.name: p for p in (OpenRouterProvider, OllamaProvider)}


def get_provider(settings: Any) -> LLMProvider:
    """Build the active provider from settings (default: OpenRouter)."""
    name = (getattr(settings, "llm_provider", "") or "openrouter").lower()
    return _PROVIDERS.get(name, OpenRouterProvider)(settings)
