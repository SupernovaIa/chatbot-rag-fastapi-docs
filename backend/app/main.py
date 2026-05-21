"""FastAPI application entrypoint.

Baseline app for Bloque A: exposes a liveness endpoint. Feature routers
(auth, chat, indexing, retrieval, evals, security) are wired in later blocks.
"""

from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness probe used by Docker healthchecks and load balancers."""
    return {"status": "ok"}
