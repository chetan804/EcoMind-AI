"""Embedding extraction with on-disk caching, plus a hand-crafted baseline feature set.

Training augmentation is applied in embedding space: each image is embedded under ``VARIANTS``
(identity, horizontal flip, vertical flip, 90-degree rotation). Labels do not change under these
transforms because waste items have no canonical orientation.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import yaml
from numpy.typing import NDArray
from PIL import Image

from ml.common.preprocessing.images import load_rgb_image
from ml.waste_classification.data.trashnet import Sample, list_samples
from ml.waste_classification.inference.embedder import TFLiteEmbedder, sha256_file
from ml.waste_classification.inference.variants import VARIANTS

REPO = Path(__file__).resolve().parents[3]
BACKBONES = REPO / "ml" / "artifacts" / "_backbones"
CACHE = REPO / "ml" / "artifacts" / "_cache"


def load_config(path: Path | None = None) -> dict:  # type: ignore[type-arg]
    return yaml.safe_load(
        (path or REPO / "ml" / "configs" / "waste_classification.yaml").read_text()
    )


def embedder_for(config: dict, name: str, threads: int = 2) -> TFLiteEmbedder:  # type: ignore[type-arg]
    return TFLiteEmbedder(BACKBONES / config["backbones"][name]["file"], threads=threads)


def backbone_embeddings(
    config: dict,  # type: ignore[type-arg]
    name: str,
    samples: list[Sample],
    variants: list[str],
) -> NDArray[np.float32]:
    """``(n_images, n_variants, dim)``; cached by (model hash, image list, variants)."""
    model_file = BACKBONES / config["backbones"][name]["file"]
    tag = hashlib.sha256(
        (sha256_file(model_file) + "|".join(s.key for s in samples) + "|".join(variants)).encode()
    ).hexdigest()[:16]
    cache_file = CACHE / f"{name}-{tag}.npy"
    if cache_file.exists():
        return np.load(cache_file)  # type: ignore[no-any-return]
    embedder = embedder_for(config, name)
    out = np.zeros((len(samples), len(variants), embedder.dimension), dtype=np.float32)
    for i, sample in enumerate(samples):
        image = load_rgb_image(sample.path.read_bytes())
        out[i] = embedder.embed([VARIANTS[v](image) for v in variants])
        if i % 500 == 0:
            print(f"  {name}: {i}/{len(samples)}", file=sys.stderr, flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(cache_file, out)
    return out


def handcrafted_features(samples: list[Sample]) -> NDArray[np.float32]:
    """Classical baseline: 4x4x4 HSV colour histogram + 8-bin gradient-orientation histogram +
    simple intensity statistics, computed on a 128x128 centre-cropped image."""
    rows = []
    for sample in samples:
        image = load_rgb_image(sample.path.read_bytes()).resize(
            (128, 128), Image.Resampling.BILINEAR
        )
        hsv = np.asarray(image.convert("HSV"), dtype=np.float32)
        hist, _ = np.histogramdd(
            hsv.reshape(-1, 3), bins=(4, 4, 4), range=((0, 256), (0, 256), (0, 256))
        )
        gray = np.asarray(image.convert("L"), dtype=np.float32)
        gy, gx = np.gradient(gray)
        magnitude, angle = np.hypot(gx, gy), np.arctan2(gy, gx)
        orient, _ = np.histogram(angle, bins=8, range=(-np.pi, np.pi), weights=magnitude)
        stats = [gray.mean() / 255, gray.std() / 255, magnitude.mean() / 255]
        rows.append(
            np.concatenate(
                [hist.ravel() / hist.sum(), orient / max(orient.sum(), 1e-9), stats]
            ).astype(np.float32)
        )
    return np.stack(rows)


def main() -> int:
    config = load_config()
    root = REPO / "datasets" / "external" / "trashnet" / "dataset-resized"
    samples = list_samples(root, config["dataset"]["classes"])
    for name in ("S", "M", "L"):
        data = backbone_embeddings(config, name, samples, config["augmentations"])
        print(f"{name}: {data.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
