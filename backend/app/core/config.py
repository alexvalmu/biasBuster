from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_role: Literal["api", "worker", "all"] = "all"
    environment: Literal["dev", "prod"] = "dev"

    database_url: str = "postgresql+asyncpg://biasbuster:biasbuster@localhost:5432/biasbuster"
    db_pool_size: int = 3
    db_max_overflow: int = 2

    cors_origins: list[str] = ["http://localhost:5173"]

    # Upload limits and cost guards
    max_upload_mb: int = 20
    max_daily_analyses: int = 200
    rate_limit_new_analyses: str = "5/day"
    max_text_chars: int = 400_000
    recaptcha_secret: str | None = None
    recaptcha_min_score: float = 0.5

    # Task dispatch: "local" calls the worker over HTTP directly, "cloudtasks" uses GCP
    tasks_backend: Literal["local", "cloudtasks"] = "local"
    worker_url: str = "http://localhost:8001"
    gcp_project: str | None = None
    gcp_location: str = "us-central1"
    gcp_tasks_queue: str = "analyses"
    tasks_service_account: str | None = None
    tasks_verify_oidc: bool = False
    max_attempts: int = 3

    # LLMs (OpenRouter, OpenAI-compatible)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model_fast: str = "qwen/qwen3-30b-a3b-instruct-2507"
    llm_model_agent: str = "deepseek/deepseek-chat-v3.1"
    llm_timeout_s: int = 120
    agent_recursion_limit: int = 16
    max_authors_investigated: int = 8

    # External data sources
    tavily_api_key: str = ""
    ncbi_api_key: str | None = None
    contact_email: str = "contact@biasbuster.app"
    open_payments_dataset_id: str | None = None
    http_cache_ttl_hours: int = 24 * 7
    http_timeout_s: float = 20.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
