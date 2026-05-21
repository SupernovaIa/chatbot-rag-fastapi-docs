"""Azure Blob Storage loader adapter.

Implements BlobLoaderPort using the azure-storage-blob SDK.
In development the SDK points to Azurite; in production the same code
points to Azure Blob real (connection string swap only).
"""

from __future__ import annotations

import logging

from azure.storage.blob import BlobServiceClient

from app.indexing.models import BlobItem
from app.indexing.ports import BlobLoaderPort

logger = logging.getLogger(__name__)


class AzuriteBlobLoader:
    """Concrete adapter over azure-storage-blob.

    Parameters
    ----------
    connection_string:
        Full Azure Storage connection string.  In local dev, use the
        well-known Azurite development connection string.
    """

    def __init__(self, connection_string: str) -> None:
        self._client = BlobServiceClient.from_connection_string(connection_string)

    # --- BlobLoaderPort ---

    def list_blobs(self, container: str) -> list[BlobItem]:
        """Return metadata for every blob in *container*."""
        container_client = self._client.get_container_client(container)
        items: list[BlobItem] = []
        for blob in container_client.list_blobs():
            items.append(
                BlobItem(
                    name=blob.name,
                    size=blob.size or 0,
                    etag=blob.etag or "",
                )
            )
        logger.info("Listed %d blobs from container '%s'", len(items), container)
        return items

    def download_blob(self, container: str, name: str) -> bytes:
        """Download and return the raw bytes of a single blob."""
        blob_client = self._client.get_blob_client(container=container, blob=name)
        data: bytes = blob_client.download_blob().readall()
        logger.debug("Downloaded blob '%s' (%d bytes)", name, len(data))
        return data

    def ensure_container(self, container: str) -> None:
        """Create *container* if it does not exist (idempotent)."""
        container_client = self._client.get_container_client(container)
        if not container_client.exists():
            container_client.create_container()
            logger.info("Created container '%s'", container)
        else:
            logger.debug("Container '%s' already exists", container)


# Make the class satisfy the Protocol at type-check time.
_: BlobLoaderPort = AzuriteBlobLoader.__new__(AzuriteBlobLoader)  # type: ignore[assignment]
