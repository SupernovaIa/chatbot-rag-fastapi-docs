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

    # Corpus snapshot pinned in SOURCE.md (idempotency key for retrieval scope).
    corpus_sha: str = "40e33e492dbf4af6172997f4e3238a32e56cbe26"

    # Models. Tier is fixed, the ID is anchored with a date (ADR-001).
    # Anchored 2026-05-21: Gemini 3.5 Flash (generation, reranker, rewriter).
    gemini_flash_model: str = "gemini-3.5-flash"

    # Retrieval tuning (specs 02/03).
    retrieval_candidates: int = 20  # top-K candidates from hybrid search
    retrieval_top_k: int = 5  # final top-K returned after rerank
    rrf_k: int = 60  # Reciprocal Rank Fusion constant
    rerank_timeout_s: float = 5.0
    rewrite_timeout_s: float = 1.5

    # Secrets (no defaults in production; placeholders ease local boot)
    google_api_key: str = ""
    jwt_secret: str = "change-me"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
