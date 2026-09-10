from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NIDAVELIR_",
        env_file=("../.env", ".env"),
        extra="ignore",
    )

    env: str = "development"
    log_level: str = "INFO"
    max_parallel_workers: int = 2
    database_url: str = "postgresql+psycopg://nidavelir:nidavelir@localhost:5432/nidavelir"
    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    worker_image: str = "nidavelir-worker:dev"
    worker_cpus: float = 1.0
    worker_memory: str = "2g"
    worker_timeout_seconds: int = 1800
    worker_stop_timeout_seconds: int = 10

    github_token: SecretStr | None = None
    openai_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
