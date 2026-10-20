"""Cross-dataset evaluation helpers: mapping discipline, metrics and the experiment plumbing."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from ml.waste_classification.research import cross_dataset as xd
from ml.waste_classification.research import multi_dataset_experiment as mde


def make_tree(root: Path, folders: list[str]) -> None:
    for name in folders:
        (root / name).mkdir(parents=True)
        (root / name / "a.jpg").write_bytes(b"x")
        (root / name / "notes.txt").write_text("not an image")


def test_collect_lists_only_images_in_a_stable_order(tmp_path: Path) -> None:
    mapping = xd.MAPPINGS["realwaste"]
    make_tree(tmp_path, list(mapping))
    files = xd.collect(tmp_path, mapping)
    assert len(files) == len(mapping)  # one image per folder, the .txt is ignored
    assert [f for f, _ in files] == sorted(mapping)


def test_collect_refuses_a_missing_or_unmapped_folder(tmp_path: Path) -> None:
    mapping = xd.MAPPINGS["realwaste"]
    make_tree(tmp_path, list(mapping)[:-1])
    with pytest.raises(SystemExit, match="missing"):
        xd.collect(tmp_path, mapping)
    full = tmp_path / "full"
    make_tree(full, [*mapping, "Batteries"])
    with pytest.raises(SystemExit, match="without a mapping"):
        xd.collect(full, mapping)


def test_every_realwaste_folder_has_an_explicit_experiment_label() -> None:
    folders = set(xd.MAPPINGS["realwaste"])
    assert folders == {
        "Cardboard",
        "Glass",
        "Metal",
        "Paper",
        "Plastic",
        "Miscellaneous Trash",
        "Food Organics",
        "Textile Trash",
        "Vegetation",
    }
    assert set(mde.RW_TO_8) == folders
    assert set(mde.RW_TO_8.values()) <= set(mde.CLASSES8)
    # the experiment taxonomy only extends the model's classes; it never renames them
    assert mde.CLASSES8[:6] == ["cardboard", "glass", "metal", "paper", "plastic", "trash"]


def test_ece_is_zero_when_confidence_equals_accuracy_and_large_when_overconfident() -> None:
    conf = np.array([0.5] * 4 + [1.0] * 4)
    calibrated = np.array([True, False, True, False, True, True, True, True])
    assert xd.expected_calibration_error(conf, calibrated) == pytest.approx(0.0)
    assert xd.expected_calibration_error(np.ones(10), np.zeros(10, dtype=bool)) == pytest.approx(1)


def test_per_class_counts_precision_recall() -> None:
    out = xd.per_class(["a", "a", "b", "b"], ["a", "b", "b", "b"], ["a", "b"])
    assert out["a"] == {"support": 2, "precision": 1.0, "recall": 0.5, "f1": 0.6667}
    assert out["b"]["recall"] == 1.0
    assert out["b"]["precision"] == pytest.approx(0.6667)


def test_summarise_reports_coverage_and_accepted_accuracy() -> None:
    rows = [
        {"mapped": "a", "pred": "a", "conf": 0.9, "review": False},
        {"mapped": "a", "pred": "b", "conf": 0.6, "review": True},
        {"mapped": "b", "pred": "b", "conf": 0.8, "review": False},
        {"mapped": "b", "pred": "a", "conf": 0.7, "review": False},
    ]
    s = xd.summarise(rows, ["a", "b"])
    assert s["n"] == 4
    assert s["accuracy"] == 0.5
    assert s["coverage_auto_accepted"] == 0.75
    assert s["accuracy_on_auto_accepted"] == pytest.approx(0.6667, abs=1e-4)
    assert s["confusion_true_rows_pred_columns"]["a"] == {"a": 1, "b": 1}


def test_scores_widen_to_all_classes_and_missing_classes_are_never_predicted() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(60, 5)).astype(np.float32)
    y = np.array([0, 2, 4] * 20)  # classes 1 and 3 absent from training
    model = LogisticRegression(max_iter=500).fit(x, y)
    wide = mde.scores(model, x, 6)
    assert wide.shape == (60, 6)
    assert set(wide.argmax(axis=1)) <= {0, 2, 4}


def test_pool_take_returns_the_requested_split() -> None:
    pool = mde.Pool(
        x=np.arange(8, dtype=np.float32).reshape(4, 2),
        y=np.array([0, 1, 0, 1]),
        group=np.array([0, 1, 2, 3]),
        split={"train": np.array([0, 1]), "val": np.array([2]), "test": np.array([3])},
    )
    x, y, g = pool.take("test")
    assert x.tolist() == [[6.0, 7.0]]
    assert y.tolist() == [1]
    assert g.tolist() == [3]
