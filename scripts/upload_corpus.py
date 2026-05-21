#!/usr/bin/env python3
"""Upload the local corpus snapshot to Azurite Blob Storage.

Usage (from repo root):
    python scripts/upload_corpus.py [--corpus-dir corpus/sample/fastapi-docs] \
                                    [--container corpus] \
                                    [--connection-string <str>]

The script is idempotent: blobs that already exist are overwritten.
Run this once before index_corpus.py.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("upload_corpus")

# Azurite dev connection string template.
# The AccountKey is the well-known public Azurite development key.
# Set AZURE_STORAGE_CONNECTION_STRING in .env or pass --connection-string.
# See: https://learn.microsoft.com/azure/storage/common/storage-use-azurite#well-known-storage-account-and-key
_AZURITE_DEV_CONN = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-dir",
        default="corpus/sample/fastapi-docs",
        help="Root directory of the corpus snapshot (default: corpus/sample/fastapi-docs)",
    )
    parser.add_argument(
        "--container",
        default="corpus",
        help="Blob container name (default: corpus)",
    )
    parser.add_argument(
        "--connection-string",
        default=os.environ.get("AZURE_STORAGE_CONNECTION_STRING", _AZURITE_DEV_CONN),
        help="Azure Storage connection string (default: Azurite dev string or env var)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        logger.error("azure-storage-blob not installed. Run: uv add azure-storage-blob")
        return 1

    corpus_path = Path(args.corpus_dir)
    if not corpus_path.is_dir():
        logger.error("Corpus directory does not exist: %s", corpus_path)
        return 1

    md_files = sorted(corpus_path.rglob("*.md"))
    # Exclude SOURCE.md from the indexed corpus (it's metadata, not content).
    md_files = [f for f in md_files if f.name != "SOURCE.md"]

    if not md_files:
        logger.warning("No .md files found in %s", corpus_path)
        return 0

    logger.info("Connecting to Blob Storage …")
    client = BlobServiceClient.from_connection_string(args.connection_string)
    container_client = client.get_container_client(args.container)

    if not container_client.exists():
        container_client.create_container()
        logger.info("Created container '%s'", args.container)

    uploaded = 0
    for md_file in md_files:
        # Relative path from corpus root becomes the blob name.
        blob_name = md_file.relative_to(corpus_path).as_posix()
        blob_client = container_client.get_blob_client(blob_name)
        with md_file.open("rb") as fh:
            blob_client.upload_blob(fh, overwrite=True)
        logger.info("  uploaded: %s", blob_name)
        uploaded += 1

    logger.info("Done. Uploaded %d blobs to container '%s'.", uploaded, args.container)
    return 0


if __name__ == "__main__":
    sys.exit(main())
