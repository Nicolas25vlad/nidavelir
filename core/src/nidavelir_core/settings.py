from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NIDAVELIR_",
        env_file=".env",
        extra="ignore",
    )

    env: str = "development"
    log_level: str = "INFO"
    max_parallel_workers: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
