"""The field-evaluation manifest gate: permission, consent, privacy, leakage, sample size."""

from __future__ import annotations

from typing import Any

import pytest

from ml.waste_classification.evaluation import field

CLASSES = ["cardboard", "glass", "metal", "paper", "plastic"]
KW: dict[str, Any] = {
    "min_images": 150,
    "prohibited": frozenset({"f" * 64}),
    "training_hashes": frozenset({"e" * 64}),
}


def _rows(per_class: int = 31) -> list[dict[str, str]]:
    rows = []
    for c in CLASSES:
        for i in range(per_class):
            rows.append(
                {
                    "file": f"{c}_{i}.jpg",
                    "sha256": f"{CLASSES.index(c)}{i:03d}".ljust(64, "a"),
                    "class": c,
                    "captured_on": "2026-11-15",
                    "site_id": "site-01",
                    "collector_id": "collector-01",
                    "permission_ref": "PERM-001",
                    "consent_ref": "no-people-in-frame",
                    "privacy_check": "yes",
                    "label_checked_by_two": "yes",
                }
            )
    return rows


def test_a_complete_manifest_is_accepted() -> None:
    assert field.manifest_problems(_rows(), CLASSES, **KW) == []


def test_an_empty_or_incomplete_manifest_is_refused() -> None:
    assert field.manifest_problems([], CLASSES, **KW)
    rows = _rows()
    del rows[0]["consent_ref"]
    assert any("missing columns" in p for p in field.manifest_problems(rows, CLASSES, **KW))


@pytest.mark.parametrize(
    ("column", "value", "expected"),
    [
        ("permission_ref", "", "empty"),
        ("permission_ref", "none", "no permission record"),
        ("consent_ref", "", "empty"),
        ("privacy_check", "no", "privacy check"),
        ("label_checked_by_two", "no", "two people"),
        ("class", "trash", "unknown class"),
        ("sha256", "xyz", "malformed"),
    ],
)
def test_each_missing_safeguard_is_refused(column: str, value: str, expected: str) -> None:
    rows = _rows()
    rows[3][column] = value
    assert any(expected in p for p in field.manifest_problems(rows, CLASSES, **KW))


def test_duplicates_prohibited_and_training_images_are_refused() -> None:
    rows = _rows()
    rows[1]["sha256"] = rows[0]["sha256"]
    rows[2]["sha256"] = "f" * 64
    rows[3]["sha256"] = "e" * 64
    problems = " | ".join(field.manifest_problems(rows, CLASSES, **KW))
    assert "duplicate" in problems and "prohibited" in problems and "leakage" in problems


def test_too_few_images_or_a_thin_class_is_refused() -> None:
    assert any("at least 150" in p for p in field.manifest_problems(_rows(10), CLASSES, **KW))
    rows = [r for r in _rows() if r["class"] != "glass"] + [
        r for r in _rows(5) if r["class"] == "glass"
    ]
    assert any("'glass'" in p for p in field.manifest_problems(rows, CLASSES, **KW))


def test_summarise_computes_metrics_from_predictions_only() -> None:
    truth = ["glass", "glass", "metal", "metal"]
    predicted = ["glass", "metal", "metal", "metal"]
    result = field.summarise(truth, predicted, [False, True, False, False], ["glass", "metal"])
    assert result["n_images"] == 4 and result["accuracy"] == 0.75
    assert result["auto_accept_rate"] == 0.75
    assert result["accuracy_of_auto_accepted"] == 1.0
    assert result["confusion_matrix"] == [[1, 1], [0, 2]]
