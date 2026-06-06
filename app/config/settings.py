from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "YenkasaCode Agent"
    app_version: str = "0.1.0"
    app_env: str = "development"
    app_port: int = 8080
    mongodb_uri: str = ""
    mongodb_database: str = "yenkasa_code"
    log_level: str = "INFO"

    @property
    def environment(self) -> str:
        return self.app_env

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
