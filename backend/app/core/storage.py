"""Object storage abstraction.

V1 ships a local-filesystem backend with content-addressed, namespaced keys
(``org/{org_id}/{uuid}.{ext}``) — one directory per organization, so
accidental cross-tenant sharing requires deliberately constructing a key.
Production swaps in S3/GCS by implementing ``StorageBackend`` (uploading and
serving remain server-authorised; pre-signed URLs are the documented next
step). Large binaries never live in PostgreSQL.
"""

from __future__ import annotations

import hashlib
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings


class StorageError(Exception):
    pass


class StorageBackend(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def open(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalFileStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Reject traversal: key must not contain ".." or leading "/"
        if not key or ".." in key.split("/") or key.startswith("/"):
            raise StorageError("Invalid storage key.")
        return (self.root / key).resolve()
        # Note: root itself is inside the workspace; resolve() keeps us honest.

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def open(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StorageError("Object not found.")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except StorageError:
            return False

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except StorageError:
            pass


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = LocalFileStorage(settings.data_dir / "uploads")
    return _storage


def media_key(organization_id, media_id, ext: str) -> str:
    return f"org/{organization_id}/{media_id}.{ext.lstrip('.')}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_media_id() -> str:
    return uuid.uuid4().hex
