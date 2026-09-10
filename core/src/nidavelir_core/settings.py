from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
