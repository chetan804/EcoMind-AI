"""The backend serving runtime must give the same answers as the ML package's own classifier.

Runs only when the trained artifact and the RealWaste images are present locally (both are
git-ignored, so CI reports this test as SKIPPED, not passed). Reproduce locally with
``python -m ml.waste_classification.data.fetch`` and ``python -m ml.waste_classification.training.train``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

from app.modules.classification.runtime import ClassifierRuntime

REPO = Path(__file__).resolve().parents[3]
ARTIFACTS = REPO / "ml" / "artifacts"
ARTIFACT_DIR = ARTIFACTS / "waste_classification" / "2.0.0"
IMAGES = REPO / "datasets" / "external" / "realwaste-src" / "RealWaste"
FOLDERS = ("Cardboard", "Glass", "Metal", "Paper", "Plastic")  # the five trained classes

pytestmark = pytest.mark.skipif(
    not (ARTIFACT_DIR / "model.json").exists() or not IMAGES.exists(),
    reason="trained artifact / RealWaste images not present (git-ignored); see module docstring",
)


def test_backend_runtime_matches_the_ml_classifier_on_real_images() -> None:
    sys.path.insert(0, str(REPO))
    try:
        # Imported dynamically: the backend project deliberately cannot see ``ml`` statically.
        classifier_module = importlib.import_module("ml.waste_classification.inference.classifier")
    finally:
        sys.path.remove(str(REPO))
    backbones = ARTIFACTS / "_backbones"
    ml_clf = classifier_module.WasteClassifier.load(ARTIFACT_DIR, backbones)
    backend = ClassifierRuntime.load(ARTIFACT_DIR, backbones)
    files = [p for c in FOLDERS for p in sorted((IMAGES / c).glob("*.jpg"))[:3]]
    assert len(files) >= 12
    for path in files:
        expected = ml_clf.predict_bytes(path.read_bytes())
        actual = backend.predict_bytes(path.read_bytes())
        assert actual.label == expected.label, path.name
        assert actual.confidence == pytest.approx(expected.confidence, abs=1e-5)
        assert actual.needs_review == expected.needs_review
        assert actual.novelty_similarity == pytest.approx(expected.novelty_similarity, abs=1e-5)
        assert np.allclose(
            list(actual.probabilities.values()), list(expected.probabilities.values()), atol=1e-5
        )
