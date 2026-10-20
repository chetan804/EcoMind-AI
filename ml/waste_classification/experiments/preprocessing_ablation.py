"""Ablation: how to turn a 4:3 photograph into the square backbone input.

    python -m ml.waste_classification.experiments.preprocessing_ablation

Compares centre-crop (the shared preprocessing), squash (distorting resize) and pad-to-square on the
TRAIN split only, with the same grouped 5-fold CV and head as the main pipeline. Validation and test
are not used. Writes ``docs/ml/reports/waste-classification-<version>-preprocessing-ablation.json``.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable

import numpy as np
from PIL import Image, ImageOps

import ml.waste_classification.inference.embedder as embedder_module
from ml.common.evaluation.metrics import macro_f1
from ml.common.preprocessing.images import load_rgb_image
from ml.waste_classification.data.trashnet import assign_folds, build_groups, list_samples
from ml.waste_classification.training import pipeline as pl
from ml.waste_classification.training.features import (
    REPO,
    backbone_embeddings,
    embedder_for,
    load_config,
)

MODES: dict[str, Callable[[Image.Image, int], Image.Image]] = {
    "centre-crop (shared preprocessing)": lambda im, s: ImageOps.fit(
        im, (s, s), Image.Resampling.BILINEAR
    ),
    "squash (distorting resize)": lambda im, s: im.resize((s, s), Image.Resampling.BILINEAR),
    "pad to square (white)": lambda im, s: ImageOps.pad(
        im, (s, s), Image.Resampling.BILINEAR, color=(255, 255, 255)
    ),
}


def main() -> int:
    config = load_config()
    seed = config["seed"]
    samples = list_samples(
        REPO / "datasets" / "external" / "trashnet" / "dataset-resized",
        config["dataset"]["classes"],
    )
    y = np.array([s.label_index for s in samples])
    grouping = backbone_embeddings(
        config, config["grouping"]["backbone"], samples, config["augmentations"]
    )
    groups = build_groups(grouping[:, 0], y, config["grouping"]["min_cosine_similarity"])
    folds = assign_folds(y, groups, n_folds=config["split"]["n_folds"], seed=seed)
    train_idx = np.flatnonzero(
        ~np.isin(folds, [config["split"]["test_fold"], config["split"]["validation_fold"]])
    )
    cv = pl.grouped_folds(y, groups, train_idx, config["selection"]["cv_folds"], seed)
    backbone = "M"
    original = embedder_module.resize_to_square
    results = {}
    try:
        for name, fn in MODES.items():
            embedder_module.resize_to_square = fn  # type: ignore[assignment]
            embedder = embedder_for(config, backbone)
            feats = np.concatenate(
                [
                    embedder.embed(
                        [load_rgb_image(s.path.read_bytes()) for s in samples[i : i + 100]]
                    )
                    for i in range(0, len(samples), 100)
                ]
            )
            feats = (feats / np.linalg.norm(feats, axis=1, keepdims=True))[:, None, :].astype(
                np.float32
            )
            scores = []
            for fit_i, held_i in cv:
                head = pl.fit_head(feats[fit_i], y[fit_i], 0.03)
                pred = pl.head_scores(head, feats[held_i])[:, 0].argmax(1)
                scores.append(macro_f1(y[held_i], pred, 6))
            results[name] = {
                "cv_macro_f1": float(np.mean(scores)),
                "cv_sem": float(np.std(scores, ddof=1) / np.sqrt(len(scores))),
            }
            print(name, results[name], file=sys.stderr, flush=True)
    finally:
        embedder_module.resize_to_square = original
    out = (
        REPO
        / "docs"
        / "ml"
        / "reports"
        / f"waste-classification-{config['version']}-preprocessing-ablation.json"
    )
    out.write_text(
        json.dumps(
            {
                "backbone": backbone,
                "C": 0.03,
                "split": "train only, grouped 5-fold CV, no augmentation",
                "results": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
