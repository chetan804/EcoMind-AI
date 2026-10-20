"""Image embedding with a quantised TFLite backbone (EfficientNet-EdgeTPU family).

Training and serving both go through ``TFLiteEmbedder`` so the features a classifier head sees in
production are produced exactly as they were during training. The backbone file is verified
against its SHA-256 before it is loaded.

Preprocessing (``prepare_image``): decode, validate, orient, RGB, scale the short side and centre
crop to ``input_size``. The pixels are then normalised as ``(x - 128) / 128`` and quantised with the
model's own input scale and zero point, which is the scheme the backbone was exported with
(verified on known photographs; see docs/ml/model-cards).
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np
from ai_edge_litert.interpreter import Interpreter
from numpy.typing import NDArray
from PIL import Image

from ml.common.preprocessing.images import resize_to_square

FloatArray = NDArray[np.float32]


class ArtifactIntegrityError(RuntimeError):
    """A model file does not match the hash recorded for it."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Embedder(Protocol):
    """What the classifier needs from a backbone (lets tests substitute a fake)."""

    def embed(self, images: Sequence[Image.Image]) -> FloatArray: ...


class TFLiteEmbedder:
    """Thread-safe (calls are serialised) embedder returning float32 vectors."""

    def __init__(self, model_path: Path, *, expected_sha256: str | None = None, threads: int = 2):
        if expected_sha256 is not None and sha256_file(model_path) != expected_sha256:
            raise ArtifactIntegrityError(f"{model_path.name} does not match its recorded SHA-256")
        self._interpreter = Interpreter(model_path=str(model_path), num_threads=threads)
        self._interpreter.allocate_tensors()
        inp = self._interpreter.get_input_details()[0]
        out = self._interpreter.get_output_details()[0]
        if inp["dtype"] != np.uint8 or out["dtype"] != np.uint8:
            raise ValueError("expected a fully quantised (uint8 in, uint8 out) embedding model")
        self._in_index, self._out_index = inp["index"], out["index"]
        self.input_size = int(inp["shape"][1])
        self.dimension = int(out["shape"][-1])
        self._in_scale, self._in_zero = (float(v) for v in inp["quantization"])
        self._out_scale, self._out_zero = (float(v) for v in out["quantization"])
        self._lock = threading.Lock()

    def _quantise(self, image: Image.Image) -> NDArray[np.uint8]:
        square = resize_to_square(image, self.input_size)
        pixels = np.asarray(square, dtype=np.float32)
        quantised = np.round((pixels - 128.0) / 128.0 / self._in_scale + self._in_zero)
        return np.clip(quantised, 0, 255).astype(np.uint8)

    def embed(self, images: Sequence[Image.Image]) -> FloatArray:
        """One embedding per image, shape ``(n, dimension)``, not normalised."""
        rows: list[FloatArray] = []
        with self._lock:
            for image in images:
                self._interpreter.set_tensor(self._in_index, self._quantise(image)[None])
                self._interpreter.invoke()
                raw = self._interpreter.get_tensor(self._out_index)[0].astype(np.float32)
                rows.append((raw - self._out_zero) * self._out_scale)
        return np.stack(rows).astype(np.float32)
