"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from the environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    app_name: str = "chatbot-rag-fastapi-docs"
    environment: str = "development"

    # Postgres + pgvector
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/chatbot_rag"

    # Azure Blob Storage (Azurite in dev, Azure Blob in prod — same SDK).
    # Must be set in .env (see .env.example and docs/azurite-setup.md).
    azure_storage_connection_string: str = ""

    # Observability
    phoenix_collector_endpoint: str = "http://phoenix:6006"

    # Secrets (no defaults in production; placeholders ease local boot)
    google_api_key: str = ""
    jwt_secret: str = "change-me"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
