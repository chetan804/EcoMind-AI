"""TrashNet loading, near-duplicate grouping and group-aware splitting.

The split is defined *before* any modelling and is a pure function of (images, seed, config), so it
is reproducible and persisted next to the evaluation report.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import AgglomerativeClustering
from sklearn.model_selection import StratifiedGroupKFold

_JUNK_PARTS = {"__MACOSX", ".DS_Store"}
_NUMBER = re.compile(r"(\d+)")


@dataclass(frozen=True)
class Sample:
    path: Path
    label: str
    label_index: int

    @property
    def key(self) -> str:
        return f"{self.label}/{self.path.name}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_dataset(zip_path: Path, destination: Path) -> None:
    """Extract the resized dataset, skipping macOS resource-fork junk and unsafe paths."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            parts = Path(member.filename).parts
            if member.is_dir() or _JUNK_PARTS.intersection(parts):
                continue
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"unsafe path in archive: {member.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))


def _sort_key(path: Path) -> tuple[int, str]:
    """Numeric file index first (``plastic2`` before ``plastic10``), then the name."""
    match = _NUMBER.search(path.stem)
    return (int(match.group(1)) if match else 0, path.name)


def list_samples(root: Path, classes: list[str]) -> list[Sample]:
    """Every ``<root>/<class>/*.jpg`` in a stable order (class, then numeric file index)."""
    samples: list[Sample] = []
    for index, label in enumerate(classes):
        folder = root / label
        files = [p for p in folder.iterdir() if p.suffix.lower() == ".jpg"]
        files.sort(key=_sort_key)
        samples.extend(Sample(path, label, index) for path in files)
    if not samples:
        raise FileNotFoundError(f"no images under {root}")
    return samples


def files_digest(samples: list[Sample]) -> str:
    """SHA-256 over sorted ``class/name sha256(file)`` lines: pins the exact dataset content."""
    lines = sorted(f"{s.key} {sha256_bytes(s.path.read_bytes())}" for s in samples)
    return sha256_bytes("\n".join(lines).encode())


def build_groups(
    embeddings: NDArray[np.float32], labels: NDArray[np.int_], min_cosine_similarity: float
) -> NDArray[np.int_]:
    """Cluster near-duplicates (several photos of one object) within each class.

    Average linkage avoids the chaining of connected components, so groups stay small.
    """
    unit = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    groups = np.zeros(len(labels), dtype=np.int_)
    offset = 0
    for label in np.unique(labels):
        members = np.flatnonzero(labels == label)
        if len(members) == 1:
            found = np.zeros(1, dtype=np.int_)
        else:
            found = AgglomerativeClustering(
                n_clusters=None,
                metric="cosine",
                linkage="average",
                distance_threshold=1.0 - min_cosine_similarity,
            ).fit_predict(unit[members])
        groups[members] = found + offset
        offset += int(np.max(found)) + 1
    return groups


def assign_folds(
    labels: NDArray[np.int_], groups: NDArray[np.int_], *, n_folds: int, seed: int
) -> NDArray[np.int_]:
    """Stratified group k-fold id per image: no group ever spans two folds."""
    folds = np.full(len(labels), -1, dtype=np.int_)
    splitter = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    for fold, (_, held_out) in enumerate(splitter.split(np.zeros(len(labels)), labels, groups)):
        folds[held_out] = fold
    return folds
