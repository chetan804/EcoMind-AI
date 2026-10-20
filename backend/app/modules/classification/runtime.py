"""Serving runtime for the waste *material* classifier.

    frozen TFLite backbone(s) -> L2-normalise -> linear head -> temperature -> calibrated softmax
    + "needs review" (low calibrated confidence, or an image unlike the training set)

This mirrors ``ml/waste_classification/inference`` on purpose: the backend image contains only
``backend/``, so it cannot import from ``ml/``. ``tests/integration/test_classification_parity.py``
checks both implementations against the real artifact. Only numpy, ai-edge-litert and Pillow are
needed (no scikit-learn, no training code). Every file is verified against the SHA-256 recorded in
``model.json`` before it is used.
"""

from __future__ import annotations

import hashlib
import io
import json
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.classification.errors import InvalidImageError, ModelUnavailableError

INPUT_SCALE = 10.0  # features are L2-normalised and multiplied by this constant (see training)
MAX_PIXELS = 50_000_000
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
VARIANTS = {
    "identity": lambda im: im,
    "hflip": lambda im: im.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
    "vflip": lambda im: im.transpose(Image.Transpose.FLIP_TOP_BOTTOM),
    "rot90": lambda im: im.transpose(Image.Transpose.ROTATE_90),
}
Float32 = NDArray[np.float32]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def decode_image(data: bytes) -> Image.Image:
    """Validated, upright RGB image (same rules as ``ml/common/preprocessing``)."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ALLOWED_FORMATS:
                raise InvalidImageError("Unsupported image format")
            if image.size[0] * image.size[1] > MAX_PIXELS:
                raise InvalidImageError("Image has too many pixels")
            image.load()
            return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("Data is not a readable image") from exc


class Embedder(Protocol):
    def embed(self, images: Sequence[Image.Image]) -> Float32: ...


class TFLiteEmbedder:
    """Quantised TFLite embedding extractor; calls are serialised (interpreters are not
    thread-safe)."""

    def __init__(self, path: Path, *, expected_sha256: str, threads: int = 2) -> None:
        from ai_edge_litert.interpreter import Interpreter

        if not path.is_file() or sha256_file(path) != expected_sha256:
            raise ModelUnavailableError("A model backbone is missing or fails its integrity check")
        self._interpreter = Interpreter(model_path=str(path), num_threads=threads)
        self._interpreter.allocate_tensors()
        inp = self._interpreter.get_input_details()[0]
        out = self._interpreter.get_output_details()[0]
        self._in_index, self._out_index = inp["index"], out["index"]
        self.input_size = int(inp["shape"][1])
        self._in_scale, self._in_zero = (float(v) for v in inp["quantization"])
        self._out_scale, self._out_zero = (float(v) for v in out["quantization"])
        self._lock = threading.Lock()

    def _quantise(self, image: Image.Image) -> NDArray[np.uint8]:
        square = ImageOps.fit(
            image, (self.input_size, self.input_size), method=Image.Resampling.BILINEAR
        )
        pixels = np.asarray(square, dtype=np.float32)
        quantised = np.round((pixels - 128.0) / 128.0 / self._in_scale + self._in_zero)
        return np.clip(quantised, 0, 255).astype(np.uint8)

    def embed(self, images: Sequence[Image.Image]) -> Float32:
        rows = []
        with self._lock:
            for image in images:
                self._interpreter.set_tensor(self._in_index, self._quantise(image)[None])
                self._interpreter.invoke()
                raw = self._interpreter.get_tensor(self._out_index)[0].astype(np.float32)
                rows.append((raw - self._out_zero) * self._out_scale)
        return np.stack(rows).astype(np.float32)


@dataclass(frozen=True)
class RawPrediction:
    label: str
    confidence: float
    probabilities: dict[str, float]
    needs_review: bool
    review_reasons: list[str] = field(default_factory=list)
    novelty_similarity: float = 0.0
    inference_ms: float = 0.0


def _softmax(logits: NDArray[np.float64], temperature: float) -> NDArray[np.float64]:
    scaled = logits / temperature
    scaled = scaled - scaled.max(axis=-1, keepdims=True)
    exp = np.exp(scaled)
    return np.asarray(exp / exp.sum(axis=-1, keepdims=True), dtype=np.float64)


class ClassifierRuntime:
    def __init__(
        self,
        manifest: dict[str, Any],
        embedders: Sequence[Embedder],
        coef: Float32,
        intercept: Float32,
        reference: Float32,
    ) -> None:
        self.manifest = manifest
        self.classes: list[str] = list(manifest["classes"])
        self._embedders = embedders
        self._coef, self._intercept, self._reference = coef, intercept, reference
        self._variants: list[str] = list(manifest["tta_variants"])
        self._temperature = float(manifest["temperature"])
        self._min_conf = float(manifest["review"]["min_confidence"])
        self._min_novelty = float(manifest["review"]["min_novelty_similarity"])

    @classmethod
    def load(cls, artifact_dir: Path, backbone_dir: Path, *, threads: int = 2) -> ClassifierRuntime:
        try:
            manifest = json.loads((artifact_dir / "model.json").read_text())
            for name, expected in manifest["files"].items():
                if sha256_file(artifact_dir / name) != expected:
                    raise ModelUnavailableError(f"{name} fails its integrity check")
            embedders = [
                TFLiteEmbedder(
                    backbone_dir / b["file"], expected_sha256=b["sha256"], threads=threads
                )
                for b in manifest["backbones"]
            ]
            head = np.load(artifact_dir / "head.npz")
            reference = np.load(artifact_dir / "novelty_reference.npy").astype(np.float32)
        except (OSError, KeyError, ValueError) as exc:
            raise ModelUnavailableError("The model artifacts could not be loaded") from exc
        return cls(manifest, embedders, head["coef"], head["intercept"], reference)

    def features(self, images: Sequence[Image.Image]) -> Float32:
        rows = []
        for image in images:
            variants = [VARIANTS[v](image) for v in self._variants]
            parts = []
            for embedder in self._embedders:
                emb = embedder.embed(variants)
                parts.append(emb / np.linalg.norm(emb, axis=1, keepdims=True))
            rows.append(np.concatenate(parts, axis=1) / np.sqrt(len(self._embedders)))
        return np.stack(rows).astype(np.float32)

    def logits(self, features: Float32) -> NDArray[np.float64]:
        scores = (features * INPUT_SCALE) @ self._coef.T + self._intercept
        return np.asarray(scores.mean(axis=1), dtype=np.float64)

    def decide(self, features: Float32, *, inference_ms: float = 0.0) -> list[RawPrediction]:
        proba = _softmax(self.logits(features), self._temperature)
        novelty = (features[:, 0] @ self._reference.T).max(axis=1)
        out = []
        for p, nov in zip(proba, novelty, strict=True):
            top = int(p.argmax())
            reasons = []
            if p[top] < self._min_conf:
                reasons.append("low_confidence")
            if nov < self._min_novelty:
                reasons.append("unfamiliar_image")
            out.append(
                RawPrediction(
                    label=self.classes[top],
                    confidence=float(p[top]),
                    probabilities={c: float(v) for c, v in zip(self.classes, p, strict=True)},
                    needs_review=bool(reasons),
                    review_reasons=reasons,
                    novelty_similarity=float(nov),
                    inference_ms=inference_ms,
                )
            )
        return out

    def predict_bytes(self, data: bytes) -> RawPrediction:
        start = time.perf_counter()
        image = decode_image(data)
        features = self.features([image])
        return self.decide(features, inference_ms=(time.perf_counter() - start) * 1000.0)[0]
