from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/proofforge"
    app_env: str = "development"

    jwt_secret: str = "change-me-in-production"
    jwt_expire_hours: int = 168  # 7 days

    resend_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    from_email: str = "noreply@proof-forge.ru"

    # SMTP (preferred transport — e.g. Gmail App Password)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""      # display From address; falls back to smtp_user
    smtp_ssl: bool = False   # True for port 465, False for 587/STARTTLS

    # LLM. We talk to OpenAI-compatible chat backends. `llm_provider` selects which one;
    # the per-provider connection lives in its own fields, and the active provider's values
    # are mirrored into the generic llm_* fields below (see model_post_init) so every caller
    # that reads settings.llm_* automatically targets the chosen backend.
    llm_provider: str = "openrouter"  # "openrouter" | "ollama"

    # Active/effective connection (resolved from the chosen provider). Defaults are the
    # OpenRouter values, kept for backward compatibility with existing LLM_* env vars.
    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "moonshotai/kimi-k2.6:free"
    llm_fallback_model: str = "google/gemma-4-31b-it:free"
    # Vision-capable models for answer attachments that include images/screenshots.
    llm_vision_model: str = "meta-llama/llama-4-maverick:free"
    llm_vision_fallback_model: str = "qwen/qwen2.5-vl-72b-instruct:free"
    llm_cost_per_1k_tokens: float = 0.0  # free tier

    # Ollama provider (local daemon or Ollama Cloud). Ollama exposes an OpenAI-compatible
    # API at {base}/chat/completions; the api key is required by clients but ignored locally
    # and used for Ollama Cloud. Cloud models use the `name:cloud` form.
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = ""
    ollama_model: str = "glm-5:cloud"
    ollama_fallback_model: str = "kimi-k2.6:cloud"
    ollama_vision_model: str = ""  # falls back to ollama_model when empty

    model_config = {"env_file": ".env", "extra": "ignore"}

    def model_post_init(self, __context) -> None:
        # Mirror the active provider's connection into the generic llm_* fields so the
        # whole codebase (which reads settings.llm_*) targets the selected backend without
        # any caller changes. OpenRouter is the default and leaves llm_* untouched.
        if (self.llm_provider or "").lower() == "ollama":
            self.llm_base_url = self.ollama_base_url
            self.llm_api_key = self.ollama_api_key
            self.llm_model = self.ollama_model
            self.llm_fallback_model = self.ollama_fallback_model
            self.llm_vision_model = self.ollama_vision_model or self.ollama_model
            self.llm_vision_fallback_model = self.ollama_fallback_model


settings = Settings()
