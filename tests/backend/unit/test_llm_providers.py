"""LLM provider abstraction: the active backend is selected by LLM_PROVIDER and the
effective llm_* connection is mirrored from it, so every caller targets one backend."""
from app.config import Settings
from app.services.llm_providers import OllamaProvider, OpenRouterProvider, get_provider


def test_openrouter_is_default_with_attribution_headers():
    s = Settings(llm_api_key="k", llm_base_url="https://openrouter.ai/api/v1", llm_model="m")
    p = get_provider(s)
    assert isinstance(p, OpenRouterProvider)
    assert p.chat_url() == "https://openrouter.ai/api/v1/chat/completions"
    h = p.headers()
    assert h["Authorization"] == "Bearer k"
    assert h["HTTP-Referer"] and h["X-Title"]  # OpenRouter attribution
    assert p.shared_rate_limited is True


def test_ollama_provider_selected_and_mirrored_into_effective_settings():
    s = Settings(
        llm_provider="ollama",
        ollama_base_url="http://host.docker.internal:11434/v1",
        ollama_api_key="sk-ollama",
        ollama_model="glm-5:cloud",
        ollama_fallback_model="kimi-k2.6:cloud",
    )
    # model_post_init mirrors the active provider into the generic llm_* fields, so
    # untouched callers reading settings.llm_* hit Ollama.
    assert s.llm_base_url == "http://host.docker.internal:11434/v1"
    assert s.llm_model == "glm-5:cloud"
    assert s.llm_fallback_model == "kimi-k2.6:cloud"

    p = get_provider(s)
    assert isinstance(p, OllamaProvider)
    assert p.chat_url() == "http://host.docker.internal:11434/v1/chat/completions"
    assert p.model == "glm-5:cloud" and p.fallback_model == "kimi-k2.6:cloud"
    h = p.headers()
    assert h["Authorization"] == "Bearer sk-ollama"
    assert "HTTP-Referer" not in h  # no OpenRouter attribution on Ollama
    assert p.shared_rate_limited is False  # own quota → no free-pool cooldown


def test_ollama_without_key_sends_no_auth_header():
    s = Settings(llm_provider="ollama", ollama_api_key="", ollama_base_url="http://localhost:11434/v1")
    p = get_provider(s)
    assert "Authorization" not in p.headers()  # local Ollama ignores the key


def test_unknown_provider_falls_back_to_openrouter():
    s = Settings(llm_provider="bogus", llm_api_key="k")
    assert isinstance(get_provider(s), OpenRouterProvider)
