from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest
from PIL import Image

from ml.waste_classification.inference.classifier import (
    INPUT_SCALE,
    WasteClassifier,
)
from ml.waste_classification.inference.embedder import (
    ArtifactIntegrityError,
    TFLiteEmbedder,
    sha256_file,
)

CLASSES = ["cardboard", "glass", "metal", "paper", "plastic", "trash"]
DIM = 12


class FakeEmbedder:
    """Maps an image's mean red value to a fixed direction, so the head's output is predictable."""

    def embed(self, images: Sequence[Image.Image]) -> npt.NDArray[np.float32]:
        rows = []
        for image in images:
            vec = np.full(DIM, 0.1, dtype=np.float32)
            vec[int(np.asarray(image)[..., 0].mean()) % 6] += 5.0
            rows.append(vec)
        return np.stack(rows)


def _classifier(
    min_conf: float = 0.5, min_novelty: float = 0.0, temperature: float = 1.0
) -> WasteClassifier:
    coef = np.zeros((6, DIM), dtype=np.float32)
    for k in range(6):
        coef[k, k] = 1.0
    unit = np.full(DIM, 0.1)
    reference = np.stack([unit / np.linalg.norm(unit)]).astype(np.float32)
    manifest = {
        "name": "waste-material-classifier",
        "version": "9.9.9",
        "classes": CLASSES,
        "tta_variants": ["identity", "hflip"],
        "temperature": temperature,
        "review": {"min_confidence": min_conf, "min_novelty_similarity": min_novelty},
    }
    return WasteClassifier(
        manifest,
        [FakeEmbedder()],
        coef,
        np.zeros(6, dtype=np.float32),
        reference,
    )


def _image(red: int) -> Image.Image:
    return Image.new("RGB", (32, 32), (red, 0, 0))


def test_predicts_the_class_the_head_scores_highest_with_a_calibrated_distribution() -> None:
    prediction = _classifier().predict_images([_image(3)])[0]
    assert prediction.label == "paper"
    assert sum(prediction.probabilities.values()) == pytest.approx(1.0)
    assert prediction.confidence == max(prediction.probabilities.values())
    assert (
        prediction.model_version == "9.9.9" and prediction.model_name == "waste-material-classifier"
    )


def test_higher_temperature_lowers_confidence_but_not_the_decision() -> None:
    sharp = _classifier(temperature=1.0).predict_images([_image(2)])[0]
    soft = _classifier(temperature=5.0).predict_images([_image(2)])[0]
    assert sharp.label == soft.label and soft.confidence < sharp.confidence


def test_low_confidence_and_unfamiliar_images_are_sent_to_review() -> None:
    confident = _classifier(min_conf=0.5).predict_images([_image(1)])[0]
    assert not confident.needs_review and confident.review_reasons == []
    strict = _classifier(min_conf=0.9999).predict_images([_image(1)])[0]
    assert strict.needs_review and strict.review_reasons == ["low_confidence"]
    unfamiliar = _classifier(min_novelty=1.5).predict_images([_image(1)])[0]
    assert unfamiliar.review_reasons == ["unfamiliar_image"]
    both = _classifier(min_conf=0.9999, min_novelty=1.5).predict_images([_image(1)])[0]
    assert both.review_reasons == ["low_confidence", "unfamiliar_image"]


def test_features_are_unit_norm_per_variant_and_scale_constant_is_documented() -> None:
    features = _classifier().features([_image(4)])
    assert features.shape == (1, 2, DIM)
    assert np.linalg.norm(features[0, 0]) == pytest.approx(1.0, abs=1e-5)
    assert INPUT_SCALE == 10.0


def test_predict_bytes_rejects_garbage() -> None:
    with pytest.raises(ValueError, match=r"."):
        _classifier().predict_bytes(b"not an image")


def _write_artifact(directory: Path) -> None:
    np.savez(
        directory / "head.npz", coef=np.zeros((6, 4), np.float32), intercept=np.zeros(6, np.float32)
    )
    np.save(directory / "novelty_reference.npy", np.zeros((1, 4), np.float16))
    files = {n: sha256_file(directory / n) for n in ("head.npz", "novelty_reference.npy")}
    (directory / "model.json").write_text(
        json.dumps({"files": files, "backbones": [], "classes": CLASSES})
    )


def test_load_refuses_a_tampered_artifact(tmp_path: Path) -> None:
    _write_artifact(tmp_path)
    with (tmp_path / "head.npz").open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(ArtifactIntegrityError, match=r"head\.npz"):
        WasteClassifier.load(tmp_path, tmp_path)


def test_embedder_refuses_a_backbone_with_the_wrong_hash(tmp_path: Path) -> None:
    fake = tmp_path / "model.tflite"
    fake.write_bytes(b"not a model")
    with pytest.raises(ArtifactIntegrityError):
        TFLiteEmbedder(fake, expected_sha256="0" * 64)
