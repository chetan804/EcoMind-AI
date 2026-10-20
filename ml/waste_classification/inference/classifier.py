"""Production inference for the waste *material* classifier.

    frozen TFLite backbone(s) -> L2-normalise -> linear head -> temperature -> calibrated softmax

plus a "needs review" decision (low calibrated confidence, or an image unlike anything seen in
training). Pure numpy + ai-edge-litert + Pillow: no scikit-learn or training code is needed to
serve. Every file is verified against the SHA-256 recorded in ``model.json`` before use.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from ml.common.evaluation.metrics import softmax
from ml.common.preprocessing.images import load_rgb_image
from ml.waste_classification.inference.embedder import (
    ArtifactIntegrityError,
    Embedder,
    TFLiteEmbedder,
    sha256_file,
)
from ml.waste_classification.inference.variants import VARIANTS

INPUT_SCALE = 10.0  # features are L2-normalised and multiplied by this constant (see training)


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float  # calibrated probability of ``label``
    probabilities: dict[str, float]
    needs_review: bool
    review_reasons: list[str] = field(default_factory=list)
    novelty_similarity: float = 0.0  # max cosine similarity to the training images
    model_name: str = ""
    model_version: str = ""


class WasteClassifier:
    def __init__(
        self,
        manifest: dict,  # type: ignore[type-arg]
        embedders: Sequence[Embedder],
        coef: NDArray[np.float32],
        intercept: NDArray[np.float32],
        reference: NDArray[np.float32],
    ):
        self.manifest = manifest
        self.classes: list[str] = manifest["classes"]
        self._embedders = embedders
        self._coef, self._intercept, self._reference = coef, intercept, reference
        self._variants: list[str] = manifest["tta_variants"]
        self._temperature = float(manifest["temperature"])
        self._min_conf = float(manifest["review"]["min_confidence"])
        self._min_novelty = float(manifest["review"]["min_novelty_similarity"])

    @classmethod
    def load(cls, artifact_dir: Path, backbone_dir: Path, *, threads: int = 2) -> WasteClassifier:
        manifest = json.loads((artifact_dir / "model.json").read_text())
        for name, expected in manifest["files"].items():
            if sha256_file(artifact_dir / name) != expected:
                raise ArtifactIntegrityError(f"{name} does not match model.json")
        embedders = [
            TFLiteEmbedder(backbone_dir / b["file"], expected_sha256=b["sha256"], threads=threads)
            for b in manifest["backbones"]
        ]
        head = np.load(artifact_dir / "head.npz")
        reference = np.load(artifact_dir / "novelty_reference.npy").astype(np.float32)
        return cls(manifest, embedders, head["coef"], head["intercept"], reference)

    # -- feature path (shared with training evaluation of robustness / parity) ---------------
    def features(self, images: list[Image.Image]) -> NDArray[np.float32]:
        """``(n_images, n_variants, dim)`` unit-norm concatenated backbone features."""
        rows = []
        for image in images:
            variants = [VARIANTS[v](image) for v in self._variants]
            parts = []
            for embedder in self._embedders:
                emb = embedder.embed(variants)
                parts.append(emb / np.linalg.norm(emb, axis=1, keepdims=True))
            rows.append(np.concatenate(parts, axis=1) / np.sqrt(len(self._embedders)))
        return np.stack(rows).astype(np.float32)

    def logits(self, features: NDArray[np.float32]) -> NDArray[np.float64]:
        """Mean over TTA variants of the linear scores, ``(n, n_classes)`` (uncalibrated)."""
        scores = (features * INPUT_SCALE) @ self._coef.T + self._intercept
        return np.asarray(scores.mean(axis=1), dtype=np.float64)

    def novelty(self, features: NDArray[np.float32]) -> NDArray[np.float64]:
        """Max cosine similarity of each image's identity features to the training images."""
        return np.asarray((features[:, 0] @ self._reference.T).max(axis=1), dtype=np.float64)

    def decide(self, features: NDArray[np.float32]) -> list[Prediction]:
        proba = softmax(self.logits(features), self._temperature)
        novelty = self.novelty(features)
        out = []
        for p, nov in zip(proba, novelty, strict=True):
            top = int(p.argmax())
            reasons = []
            if p[top] < self._min_conf:
                reasons.append("low_confidence")
            if nov < self._min_novelty:
                reasons.append("unfamiliar_image")
            out.append(
                Prediction(
                    label=self.classes[top],
                    confidence=float(p[top]),
                    probabilities={c: float(v) for c, v in zip(self.classes, p, strict=True)},
                    needs_review=bool(reasons),
                    review_reasons=reasons,
                    novelty_similarity=float(nov),
                    model_name=self.manifest["name"],
                    model_version=self.manifest["version"],
                )
            )
        return out

    # -- public API -------------------------------------------------------------------------
    def predict_images(self, images: list[Image.Image]) -> list[Prediction]:
        return self.decide(self.features(images))

    def predict_bytes(self, data: bytes) -> Prediction:
        """Decode (validated, size-capped) and classify one encoded image."""
        return self.predict_images([load_rgb_image(data)])[0]

    def timed_predict_bytes(self, data: bytes) -> tuple[Prediction, float]:
        start = time.perf_counter()
        prediction = self.predict_bytes(data)
        return prediction, (time.perf_counter() - start) * 1000.0
