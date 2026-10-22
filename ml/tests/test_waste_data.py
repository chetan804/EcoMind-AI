from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ml.waste_classification.data.imagefolder import (
    assign_folds,
    build_groups,
    files_digest,
    list_out_of_scope,
    list_samples,
)

CLASSES = ["cardboard", "glass"]
LABEL_MAP: dict[str, str | None] = {"Cardboard": "cardboard", "Glass": "glass", "Misc": None}


def _tree(root: Path) -> None:
    for folder in LABEL_MAP:
        (root / folder).mkdir()
    for name in ("Glass_10.jpg", "Glass_2.jpg", "Glass_1.jpg", "notes.txt"):
        (root / "Glass" / name).write_bytes(b"x")
    (root / "Cardboard" / "Cardboard_1.jpg").write_bytes(b"x")
    (root / "Misc" / "Misc_1.jpg").write_bytes(b"m")


def test_list_samples_orders_numerically_and_ignores_non_images(tmp_path: Path) -> None:
    _tree(tmp_path)
    samples = list_samples(tmp_path, LABEL_MAP, CLASSES)
    assert [s.key for s in samples] == [
        "Cardboard/Cardboard_1.jpg",
        "Glass/Glass_1.jpg",
        "Glass/Glass_2.jpg",
        "Glass/Glass_10.jpg",
    ]
    assert [s.label_index for s in samples] == [0, 1, 1, 1]


def test_a_catch_all_folder_is_never_a_training_sample_but_is_listed_out_of_scope(
    tmp_path: Path,
) -> None:
    _tree(tmp_path)
    assert all(s.folder != "Misc" for s in list_samples(tmp_path, LABEL_MAP, CLASSES))
    assert [(f, p.name) for f, p in list_out_of_scope(tmp_path, LABEL_MAP)] == [
        ("Misc", "Misc_1.jpg")
    ]


def test_a_folder_without_an_explicit_mapping_decision_is_refused(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "Textile").mkdir()
    with pytest.raises(ValueError, match="without a mapping decision"):
        list_samples(tmp_path, LABEL_MAP, CLASSES)


def test_a_mapping_to_an_unknown_class_or_a_missing_folder_is_refused(tmp_path: Path) -> None:
    _tree(tmp_path)
    with pytest.raises(ValueError, match="do not exist"):
        list_samples(tmp_path, {**LABEL_MAP, "Glass": "trash"}, CLASSES)
    with pytest.raises(FileNotFoundError, match="missing"):
        list_samples(tmp_path, {**LABEL_MAP, "Metal": "glass"}, CLASSES)


def test_files_digest_depends_on_content_not_order(tmp_path: Path) -> None:
    for label in CLASSES:
        (tmp_path / label).mkdir()
        (tmp_path / label / f"{label}1.jpg").write_bytes(label.encode())
    samples = list_samples(tmp_path, {"cardboard": "cardboard", "glass": "glass"}, CLASSES)
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
