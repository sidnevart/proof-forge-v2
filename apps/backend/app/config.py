from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/proofforge"
    app_env: str = "development"

    jwt_secret: str = "change-me-in-production"
    jwt_expire_hours: int = 168  # 7 days

    resend_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    from_email: str = "noreply@proof-forge.ru"

    # LLM (OpenAI-compatible, works with Together/OpenRouter/local Ollama)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.together.xyz/v1"
    llm_model: str = "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
