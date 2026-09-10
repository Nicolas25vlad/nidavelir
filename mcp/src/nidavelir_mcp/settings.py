from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NIDAVELIR_MCP_",
        env_file=("../.env", ".env"),
        extra="ignore",
    )

    core_url: str = "http://127.0.0.1:8000"
    transport: Literal["stdio", "streamable-http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8001
    request_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
