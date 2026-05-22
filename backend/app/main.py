"""FastAPI application entrypoint.

Exposes a liveness endpoint, the retrieval router and the chat router. Tracing
is initialised at startup (OpenTelemetry → Phoenix, OpenInference for
LangChain; ADR-008). Feature routers (auth, evals, security) are wired in
later blocks.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.config import get_settings
from app.observability.tracing import setup_tracing
from app.retrieval.router import router as retrieval_router

settings = get_settings()

# Best-effort: no-ops if Phoenix or the tracing libs are unavailable.
setup_tracing(endpoint=settings.phoenix_collector_endpoint)

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(retrieval_router)
app.include_router(chat_router)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness probe used by Docker healthchecks and load balancers."""
    return {"status": "ok"}
