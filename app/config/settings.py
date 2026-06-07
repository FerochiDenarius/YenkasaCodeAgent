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
    mongodb_database: str = "yenkasa_ai_db"
    mongodb_app_database: str = "yenkasaChat"
    baleshop_database_url: str = ""
    baleshop_database_name: str = "yenkasa_store"
    baleshop_database_label: str = "yenkasa_store"
    vertex_project_id: str = ""
    vertex_location: str = "us-central1"
    vertex_embedding_model: str = "gemini-embedding-001"
    google_cloud_project: str = "project-10405180-0afd-4ecc-9f8"
    google_application_credentials: str = ""
    cloud_run_service: str = ""
    log_level: str = "INFO"
    admin_api_key: str = "dev-admin-key"
    developer_api_key: str = "dev-developer-key"
    viewer_api_key: str = "dev-viewer-key"
    api_keys: str = ""
    max_request_bytes: int = 65_536
    max_query_length: int = 2_000
    max_context_keys: int = 50
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 20
    expensive_rate_limit_per_minute: int = 20
    external_timeout_seconds: float = 10.0
    mongodb_server_selection_timeout_ms: int = 5_000
    mongodb_socket_timeout_ms: int = 10_000
    mongodb_max_pool_size: int = 50
    mongodb_aggregate_limit: int = 100
    cloud_run_location: str = "us-central1"

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
