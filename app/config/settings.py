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
    vertex_project_id: str = ""
    vertex_location: str = "us-central1"
    vertex_embedding_model: str = "gemini-embedding-001"
    google_cloud_project: str = "project-10405180-0afd-4ecc-9f8"
    google_application_credentials: str = ""
    cloud_run_service: str = ""
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
