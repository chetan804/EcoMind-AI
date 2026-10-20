"""File storage integration: where uploaded media bytes live.

Module services depend on the ``FileStorage`` protocol, never on a concrete backend. Only the
local-filesystem backend exists (``FILE_STORAGE_BACKEND=local``); an S3-compatible backend would
implement the same three methods.
"""

from __future__ import annotations

from app.integrations.file_storage.base import FileStorage, StorageError
from app.integrations.file_storage.local import LocalFileStorage

__all__ = ["FileStorage", "LocalFileStorage", "StorageError"]
