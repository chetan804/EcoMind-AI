from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pytest

from ml.waste_classification.data.trashnet import (
    assign_folds,
    build_groups,
    extract_dataset,
    files_digest,
    list_samples,
)

CLASSES = ["cardboard", "glass"]


def _make_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


def test_extract_skips_macos_junk_and_keeps_images(tmp_path: Path) -> None:
    archive = tmp_path / "d.zip"
    _make_zip(
        archive,
        {
            "dataset-resized/glass/glass1.jpg": b"a",
            "__MACOSX/dataset-resized/glass/._glass1.jpg": b"junk",
            "dataset-resized/.DS_Store": b"junk",
        },
    )
    extract_dataset(archive, tmp_path / "out")
    found = sorted(
        p.relative_to(tmp_path / "out").as_posix()
        for p in (tmp_path / "out").rglob("*")
        if p.is_file()
    )
    assert found == ["dataset-resized/glass/glass1.jpg"]


def test_extract_refuses_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    _make_zip(archive, {"../escape.jpg": b"x"})
    with pytest.raises(ValueError, match="unsafe path"):
        extract_dataset(archive, tmp_path / "out")
    assert not (tmp_path / "escape.jpg").exists()


def test_list_samples_orders_numerically_and_ignores_non_jpg(tmp_path: Path) -> None:
    for label in CLASSES:
        (tmp_path / label).mkdir()
    for name in ("glass10.jpg", "glass2.jpg", "glass1.jpg", "notes.txt"):
        (tmp_path / "glass" / name).write_bytes(b"x")
    (tmp_path / "cardboard" / "cardboard1.jpg").write_bytes(b"x")
    samples = list_samples(tmp_path, CLASSES)
    assert [s.key for s in samples] == [
        "cardboard/cardboard1.jpg",
        "glass/glass1.jpg",
        "glass/glass2.jpg",
        "glass/glass10.jpg",
    ]
    assert [s.label_index for s in samples] == [0, 1, 1, 1]


def test_files_digest_depends_on_content_not_order(tmp_path: Path) -> None:
    for label in CLASSES:
        (tmp_path / label).mkdir()
        (tmp_path / label / f"{label}1.jpg").write_bytes(label.encode())
    samples = list_samples(tmp_path, CLASSES)
    first = files_digest(samples)
    assert files_digest(list(reversed(samples))) == first
    (tmp_path / "glass" / "glass1.jpg").write_bytes(b"changed")
    assert files_digest(samples) != first


def _embeddings() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)
    centres = rng.normal(size=(40, 32))
    rows, labels = [], []
    for i, centre in enumerate(centres):
        for _ in range(3):  # three near-identical "photos" of each object
            rows.append(centre + rng.normal(scale=0.01, size=32))
            labels.append(i % 2)
    return np.array(rows, dtype=np.float32), np.array(labels)


def test_build_groups_clusters_near_duplicates_and_never_crosses_classes() -> None:
    emb, labels = _embeddings()
    groups = build_groups(emb, labels, 0.9)
    assert len(np.unique(groups)) == 40
    for g in np.unique(groups):
        assert len(set(labels[groups == g])) == 1
        assert (groups == g).sum() == 3
    # identical vectors in different classes stay in different groups
    two = np.vstack([emb[:1], emb[:1]])
    assert len(set(build_groups(two, np.array([0, 1]), 0.9))) == 2


def test_assign_folds_keeps_groups_whole_and_stratified() -> None:
    emb, labels = _embeddings()
    groups = build_groups(emb, labels, 0.9)
    folds = assign_folds(labels, groups, n_folds=4, seed=1)
    assert set(folds) == {0, 1, 2, 3}
    for g in np.unique(groups):
        assert len(set(folds[groups == g])) == 1
    counts = [np.bincount(labels[folds == f], minlength=2) for f in range(4)]
    assert all(abs(c[0] - c[1]) <= 3 for c in counts)
    assert assign_folds(labels, groups, n_folds=4, seed=1).tolist() == folds.tolist()
