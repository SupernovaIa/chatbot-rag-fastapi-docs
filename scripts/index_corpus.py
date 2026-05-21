#!/usr/bin/env python3
"""Index the FastAPI docs corpus into pgvector.

Usage (from repo root or inside the Docker container):
    python scripts/index_corpus.py [--corpus-sha <sha>] [--dry-run]

The script is idempotent: re-running it with the same corpus SHA skips
already-indexed chunks (ON CONFLICT DO NOTHING on chunk_hash).

Before running:
    1. Upload corpus to Azurite:   python scripts/upload_corpus.py
    2. Apply DB migrations:        alembic upgrade head
    3. Set GOOGLE_API_KEY in env.

Environment variables:
    GOOGLE_API_KEY               (required) Google AI Studio key.
    DATABASE_URL                 Postgres connection string (default: Docker service).
    AZURE_STORAGE_CONNECTION_STRING  Azurite connection string (default: dev string).
    CORPUS_SHA                   Corpus commit SHA (overrides --corpus-sha).
    BATCH_SIZE                   Embedding batch size (default: 50).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Allow running from both the repo root and inside backend/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("index_corpus")

# Corpus SHA from SOURCE.md (pinned to 2026-05-21 snapshot).
_DEFAULT_CORPUS_SHA = "40e33e492dbf4af6172997f4e3238a32e56cbe26"

# Connection string must be set via AZURE_STORAGE_CONNECTION_STRING env var.
# See .env.example and https://learn.microsoft.com/azure/storage/common/storage-use-azurite
_AZURITE_DEV_CONN = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")

_DATABASE_URL_DEFAULT = (
    "postgresql+psycopg://postgres:postgres@localhost:5432/chatbot_rag"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-sha",
        default=os.environ.get("CORPUS_SHA", _DEFAULT_CORPUS_SHA),
        help="Corpus commit SHA used as idempotency key (default: pinned SHA in SOURCE.md)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Split and embed but do not write to the DB",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("BATCH_SIZE", "50")),
        help="Embedding batch size (default: 50)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    google_api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not google_api_key:
        logger.error("GOOGLE_API_KEY is not set. Export it before running.")
        return 1

    database_url = os.environ.get("DATABASE_URL", _DATABASE_URL_DEFAULT)
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")

    if not connection_string:
        logger.error(
            "AZURE_STORAGE_CONNECTION_STRING is not set. "
            "Copy .env.example to .env and fill in the Azurite connection string. "
            "See docs/azurite-setup.md for the well-known development key."
        )
        return 1

    try:
        from sqlalchemy import create_engine

        from app.indexing.embeddings import GeminiEmbeddingsAdapter
        from app.indexing.loader import AzuriteBlobLoader
        from app.indexing.pipeline import run_indexing
        from app.indexing.store import PgVectorChunkStore
    except ImportError as exc:
        logger.error("Import failed: %s. Are you running from inside the backend?", exc)
        return 1

    logger.info("Connecting to Postgres …")
    engine = create_engine(database_url, pool_pre_ping=True)

    loader = AzuriteBlobLoader(connection_string)
    embeddings = GeminiEmbeddingsAdapter(
        api_key=google_api_key,
        batch_size=args.batch_size,
    )
    store = PgVectorChunkStore(engine)

    logger.info(
        "Starting indexing. corpus_sha=%s dry_run=%s batch_size=%d",
        args.corpus_sha,
        args.dry_run,
        args.batch_size,
    )

    result = run_indexing(
        loader=loader,
        embeddings=embeddings,
        store=store,
        corpus_sha=args.corpus_sha,
        dry_run=args.dry_run,
    )

    logger.info("=== Indexing result ===")
    for key, value in result.items():
        logger.info("  %s: %s", key, value)

    if not args.dry_run and result["total_in_store"] < 100:
        logger.warning(
            "Fewer than 100 chunks in store (%d). Check Azurite blobs and API key.",
            result["total_in_store"],
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
