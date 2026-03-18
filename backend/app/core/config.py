from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mianshibao"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg_async://postgres:postgres@postgres:5432/mianshibao"
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_resume_bucket: str = "resume-files"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7
    dashscope_api_key: str = ""
    resume_score_timeout_seconds: int = 90
    resume_score_max_chars: int = 7000

    llm_scenario_configs: dict[str, dict[str, Any]] = Field(
        default_factory=lambda: {
            "RESUME_PARSING": {"provider": "qwen", "model": "qwen-max", "temperature": 0.0},
            "INTERVIEW": {"provider": "qwen", "model": "qwen-max", "temperature": 0.7},
            "RAG": {"provider": "qwen", "model": "qwen-plus", "temperature": 0.3},
            "DEFAULT": {"provider": "fallback", "model": "fallback", "temperature": 0.5},
        }
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
