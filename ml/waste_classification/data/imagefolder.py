"""Image-folder loading, near-duplicate grouping and group-aware splitting.

Generic over datasets laid out as ``<root>/<folder>/*.jpg``. A *label map* says which source folder
becomes which EcoMind class; a folder mapped to ``None`` is out of scope (never trained on, never
given a label) and is only listed separately for review-routing evaluation.

The split is defined *before* any modelling and is a pure function of (images, seed, config), so it
is reproducible and persisted next to the evaluation report.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import AgglomerativeClustering
from sklearn.model_selection import StratifiedGroupKFold

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_NUMBER = re.compile(r"(\d+)")


@dataclass(frozen=True)
class Sample:
    path: Path
    label: str  # EcoMind class name (never a raw source label)
    label_index: int

    @property
    def folder(self) -> str:
        """The source folder the file came from (the dataset's own label)."""
        return self.path.parent.name

    @property
    def key(self) -> str:
        return f"{self.folder}/{self.path.name}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sort_key(path: Path) -> tuple[int, str]:
    """Numeric file index first (``Plastic_2`` before ``Plastic_10``), then the name."""
    match = _NUMBER.search(path.stem)
    return (int(match.group(1)) if match else 0, path.name)


def list_folder(folder: Path) -> list[Path]:
    """Every image file of one folder in a stable order."""
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    files.sort(key=_sort_key)
    return files


def check_label_map(root: Path, label_map: dict[str, str | None], classes: list[str]) -> None:
    """Every folder needs an explicit mapping decision; every mapped class must be a known class."""
    present = {p.name for p in root.iterdir() if p.is_dir()}
    if unmapped := sorted(present - set(label_map)):
        raise ValueError(f"folders without a mapping decision: {unmapped}")
    if missing := sorted(set(label_map) - present):
        raise FileNotFoundError(f"mapped folders missing under {root}: {missing}")
    if unknown := sorted({c for c in label_map.values() if c is not None} - set(classes)):
        raise ValueError(f"label map targets classes that do not exist: {unknown}")


def list_samples(root: Path, label_map: dict[str, str | None], classes: list[str]) -> list[Sample]:
    """Training-scope samples: folders mapped to a class, ordered by (class, folder, file index)."""
    check_label_map(root, label_map, classes)
    samples: list[Sample] = []
    for index, label in enumerate(classes):
        for folder in sorted(f for f, target in label_map.items() if target == label):
            samples.extend(Sample(p, label, index) for p in list_folder(root / folder))
    if not samples:
        raise FileNotFoundError(f"no images under {root}")
    return samples


def list_out_of_scope(root: Path, label_map: dict[str, str | None]) -> list[tuple[str, Path]]:
    """``(source folder, file)`` for folders deliberately given no EcoMind class."""
    out: list[tuple[str, Path]] = []
    for folder in sorted(f for f, target in label_map.items() if target is None):
        out.extend((folder, p) for p in list_folder(root / folder))
    return out


def files_digest(samples: list[Sample]) -> str:
    """SHA-256 over sorted ``folder/name sha256(file)`` lines: pins the exact dataset content."""
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
