"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import model_validator
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
    # Gemini 3 Pro: evals judge only (RAGAS, ADR-007). A different model than the
    # generator (Flash) to reduce self-approval bias; same provider (partial).
    # Anchored 2026-05-24: the API exposes the Pro tier as `gemini-3-pro-preview`
    # (there is no bare `gemini-3-pro` id — it 404s).
    gemini_pro_model: str = "gemini-3-pro-preview"

    # Retrieval tuning (specs 02/03).
    # The Gemini API enforces a minimum request deadline of 10s; the original
    # spec-03 values (rerank 5s, rewrite 1.5s) are now rejected with 400
    # INVALID_ARGUMENT, so the LLM-reranker/rewriter always fell back. Measured
    # over the gold subset: a 20- or 10-candidate listwise prompt still hit 504
    # (p95 ~123s with SDK retries); 8 candidates lands at p50 10.0s / p95 10.9s /
    # max 12.5s with 0/7 fallbacks. So: 8 candidates, 15s budget, no SDK retries
    # (retries turned a 504 into a ~2min stall instead of a fast fallback).
    retrieval_candidates: int = 8  # candidates fed to the LLM reranker (was 20)
    retrieval_top_k: int = 5  # final top-K returned after rerank
    rrf_k: int = 60  # Reciprocal Rank Fusion constant
    rerank_timeout_s: float = 15.0  # listwise rerank over 8 candidates (>=10s API min)
    rewrite_timeout_s: float = 10.0  # multi-turn rewrite (>=10s API min)
    rerank_max_retries: int = 0  # fail fast to hybrid order; no SDK backoff stall

    # Chat / generation (specs 05/06/07).
    generate_timeout_s: float = 60.0  # max wall-clock time for one generation
    history_window_n: int = 5  # sliding window: last N complete turns (ADR-005)

    # Evals (spec 10 / ADR-007). The judge (Gemini Pro) free tier is tight, so
    # the runner throttles RAGAS concurrency and backs off on rate limits.
    evals_judge_max_workers: int = 2  # RAGAS RunConfig concurrency cap
    evals_judge_timeout_s: float = 300.0  # per-metric judge call timeout (Pro is slow)
    evals_gen_timeout_s: float = 60.0  # answer-generation timeout per example

    # Secrets (no defaults in production; placeholders ease local boot)
    google_api_key: str = ""
    jwt_secret: str = "change-me"

    # JWT token lifetimes (ADR-006)
    jwt_access_ttl_s: int = 3600        # 1 hour
    jwt_refresh_ttl_s: int = 604800     # 7 days

    # CORS (ADR-006): set CORS_ORIGINS in production to restrict allowed origins.
    # The default value covers the Vite dev server; override via env var:
    #   CORS_ORIGINS='["https://app.example.com"]'
    cors_origins: list[str] = ["http://localhost:5173"]

    @model_validator(mode="after")
    def _require_jwt_secret_in_prod(self) -> "Settings":
        """Fail fast if JWT_SECRET is the insecure placeholder outside development."""
        if self.environment != "development" and self.jwt_secret == "change-me":
            raise ValueError(
                "JWT_SECRET must be set to a strong secret in non-development environments. "
                "The default 'change-me' value is not allowed in production."
            )
        return self

    @property
    def cookie_secure(self) -> bool:
        """True in production (HTTPS only); False in development to allow plain HTTP."""
        return self.environment != "development"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
