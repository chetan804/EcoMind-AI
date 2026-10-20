from __future__ import annotations

from typing import Protocol


class StorageError(Exception):
    """The storage backend could not complete the operation (I/O error, missing key, bad key)."""


class FileStorage(Protocol):
    def save(self, key: str, content: bytes) -> None:
        """Store ``content`` under ``key``; must be atomic (no partial file is ever readable)."""

    def read(self, key: str) -> bytes:
        """Return the bytes stored under ``key`` or raise ``StorageError``."""

    def delete(self, key: str) -> None:
        """Remove ``key``. Deleting a missing key is not an error."""
