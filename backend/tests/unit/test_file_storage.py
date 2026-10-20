from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from app.integrations.file_storage import LocalFileStorage, StorageError
from app.integrations.file_storage.local import new_storage_key

GOOD = "ab/12345678-1234-1234-1234-123456789abc.png"


def test_round_trip_and_idempotent_delete(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    storage.save(GOOD, b"bytes")
    assert storage.read(GOOD) == b"bytes"
    storage.delete(GOOD)
    storage.delete(GOOD)  # deleting a missing key is not an error
    with pytest.raises(StorageError):
        storage.read(GOOD)


def test_generated_keys_are_accepted_and_unique(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    keys = {new_storage_key("jpg") for _ in range(50)}
    assert len(keys) == 50
    for key in keys:
        storage.save(key, b"x")
    with pytest.raises(ValueError):
        new_storage_key("php")


@pytest.mark.parametrize(
    "key",
    [
        "../escape.png",
        "ab/../../escape.png",
        "/etc/passwd",
        "C:\\windows\\x.png",
        "ab/12345678-1234-1234-1234-123456789abc.php",
        "ab/12345678-1234-1234-1234-123456789abc.png/../x",
        "ab/../12345678-1234-1234-1234-123456789abc.png",
        "photo.png",
        "",
        "ab/12345678-1234-1234-1234-123456789abc.png\x00.jpg",
        GOOD.upper(),
    ],
)
def test_keys_outside_the_allow_list_are_refused_for_every_operation(
    tmp_path: Path, key: str
) -> None:
    storage = LocalFileStorage(tmp_path)
    for operation in (
        lambda: storage.save(key, b"x"),
        lambda: storage.read(key),
        lambda: storage.delete(key),
    ):
        with pytest.raises(StorageError, match="invalid storage key"):
            operation()


def test_a_symlinked_shard_cannot_lead_outside_the_root(tmp_path: Path) -> None:
    root, outside = tmp_path / "root", tmp_path / "outside"
    outside.mkdir()
    storage = LocalFileStorage(root)
    (root / "ab").symlink_to(outside, target_is_directory=True)
    with pytest.raises(StorageError, match="invalid storage key"):
        storage.save(GOOD, b"x")
    assert list(outside.iterdir()) == []


def test_files_are_private_and_no_temp_file_is_left_behind(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    storage.save(GOOD, b"x")
    mode = stat.S_IMODE((tmp_path / GOOD).stat().st_mode)
    assert mode == 0o600
    assert [p.name for p in (tmp_path / "ab").iterdir()] == [Path(GOOD).name]


def test_failed_write_leaves_neither_partial_file_nor_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = LocalFileStorage(tmp_path)

    def boom(src: str, dst: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(StorageError, match="could not write"):
        storage.save(GOOD, b"x")
    assert [p for p in (tmp_path / "ab").iterdir()] == []
