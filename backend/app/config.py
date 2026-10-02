"""Runtime configuration.

All settings are environment-driven (prefix ``ARENA_``) so secrets never live in
source control. Defaults are safe for fully-offline local development: the
``mock`` provider requires no network access and no API keys.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARENA_", env_file=".env", extra="ignore")

    app_name: str = "AI Werewolf Arena"

    # LLM provider: mock | ollama | openai
    llm_provider: str = "mock"

    # Ollama (local inference, default for real models)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # OpenAI-compatible endpoint (OpenAI, Azure OpenAI, vLLM, ...)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Generation + guardrails
    max_output_tokens: int = 400
    temperature: float = 0.7
    guardrail_max_retries: int = 2

    # Episodic memory retrieval
    memory_top_k: int = 5

    # Game rules
    max_rounds: int = 20
    human_action_timeout_seconds: int = 600

    # Serving
    static_dir: str = "static"
    cors_origins: str = "*"


settings = Settings()
