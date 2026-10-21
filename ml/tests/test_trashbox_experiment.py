"""The TrashBox experiment's guard rails (no real data needed)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ml.waste_classification.research import trashbox_experiment as tbx


def _tree(root: Path, per_folder: int) -> Path:
    for folder in tbx.TB_FOLDERS:
        (root / folder).mkdir(parents=True)
        for i in range(per_folder):
            (root / folder / f"{folder} {i}.jpg").write_bytes(b"x")
        (root / folder / "notes.txt").write_text("not an image")
    return root


def test_pick_trashbox_is_capped_deterministic_and_maps_labels(tmp_path: Path) -> None:
    root = _tree(tmp_path / "tb", 12)
    first, audit = tbx.pick_trashbox(root, per_class=5, seed=7)
    again, _ = tbx.pick_trashbox(root, per_class=5, seed=7)
    other, _ = tbx.pick_trashbox(root, per_class=5, seed=8)
    assert [s.key for s in first] == [s.key for s in again]
    assert [s.key for s in first] != [s.key for s in other]
    assert audit["available"] == {label: 12 for label in tbx.TB_FOLDERS.values()}
    assert audit["selected"] == {label: 5 for label in tbx.TB_FOLDERS.values()}
    assert {s.label for s in first} == set(tbx.TB_FOLDERS.values())
    assert all(s.path.suffix == ".jpg" for s in first)  # the notes file is never picked
    assert all(tbx.CLASSES[s.label_index] == s.label for s in first)


def test_taxonomy_extends_trashnet_with_the_two_trashbox_only_classes() -> None:
    assert tbx.CLASSES[:6] == ["cardboard", "glass", "metal", "paper", "plastic", "trash"]
    assert tbx.CLASSES[6:] == ["e_waste", "medical"]
    assert set(tbx.TB_FOLDERS.values()) <= set(tbx.CLASSES)
    assert "trash" not in tbx.TB_FOLDERS.values()  # TrashBox has no such class


def test_refuses_to_overwrite_a_recorded_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "result.json"
    out.write_text("{}")
    monkeypatch.setattr(sys, "argv", ["x", "--trashbox-root", str(tmp_path), "--out", str(out)])
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        tbx.main()
    assert out.read_text() == "{}"
