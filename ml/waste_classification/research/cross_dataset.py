"""Evaluate a trained classifier on a dataset it never saw (cross-dataset generalisation).

The model is only *evaluated* here: nothing is fitted, calibrated or thresholded on this data, so
the numbers are an honest out-of-distribution test. Labels of the external dataset are mapped to
the model's classes with an explicit, reviewable table (`MAPPINGS`); classes the model cannot
predict are reported separately as "out of scope" (the share the review rule sends to a person)
and never counted as errors.

    PYTHONPATH=. python -m ml.waste_classification.research.cross_dataset realwaste \\
        --root datasets/external/realwaste-src/RealWaste \\
        --reference-hashes <json list of training-image sha256> \\
        --out docs/ml/dataset-research/experiments/cross-dataset-realwaste.json

Images are decoded with the same validated loader as serving; files that fail to decode are
counted and listed, not skipped silently. Order is sorted, so reruns on the same files give
identical output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from ml.common.preprocessing.images import load_rgb_image
from ml.waste_classification.inference.classifier import WasteClassifier

# external folder name -> model class, or None when the model has no such class (out of scope).
MAPPINGS: dict[str, dict[str, str | None]] = {
    "realwaste": {
        "Cardboard": "cardboard",
        "Glass": "glass",
        "Metal": "metal",
        "Paper": "paper",
        "Plastic": "plastic",
        # Approximate: RealWaste's "Miscellaneous Trash" is a catch-all class; TrashNet's "trash"
        # is mostly non-recyclable items on a plain background. Equivalence is not established, so
        # results are reported with and without it.
        "Miscellaneous Trash": "trash",
        "Food Organics": None,
        "Textile Trash": None,
        "Vegetation": None,
    }
}
APPROXIMATE = {"realwaste": {"Miscellaneous Trash"}}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect(root: Path, mapping: dict[str, str | None]) -> list[tuple[str, Path]]:
    missing = [name for name in mapping if not (root / name).is_dir()]
    if missing:
        raise SystemExit(f"Folders missing under {root}: {missing}")
    unknown = sorted(p.name for p in root.iterdir() if p.is_dir() and p.name not in mapping)
    if unknown:
        raise SystemExit(f"Folders without a mapping decision: {unknown}")
    files: list[tuple[str, Path]] = []
    for name in sorted(mapping):
        files.extend(
            (name, p) for p in sorted((root / name).iterdir()) if p.suffix.lower() in IMAGE_SUFFIXES
        )
    return files


def expected_calibration_error(
    conf: NDArray[np.float64], correct: NDArray[np.bool_], bins: int = 10
) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total, err = len(conf), 0.0
    for lo, hi in pairwise(edges):
        mask = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if mask.any():
            err += mask.sum() / total * abs(float(correct[mask].mean()) - float(conf[mask].mean()))
    return float(err)


def per_class(
    true: list[str], pred: list[str], classes: list[str]
) -> dict[str, dict[str, float | int]]:
    out: dict[str, dict[str, float | int]] = {}
    for c in classes:
        tp = sum(1 for t, p in zip(true, pred, strict=True) if t == c and p == c)
        fp = sum(1 for t, p in zip(true, pred, strict=True) if t != c and p == c)
        fn = sum(1 for t, p in zip(true, pred, strict=True) if t == c and p != c)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out[c] = {
            "support": tp + fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return out


def bootstrap_ci(values: NDArray[np.bool_], seed: int = 0, rounds: int = 2000) -> list[float]:
    rng = np.random.default_rng(seed)
    n = len(values)
    means = [float(values[rng.integers(0, n, n)].mean()) for _ in range(rounds)]
    return [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]


def summarise(rows: list[dict[str, Any]], classes: list[str]) -> dict[str, Any]:
    true = [r["mapped"] for r in rows]
    pred = [r["pred"] for r in rows]
    correct = np.array([t == p for t, p in zip(true, pred, strict=True)])
    conf = np.array([r["conf"] for r in rows])
    accepted = np.array([not r["review"] for r in rows])
    pc = per_class(true, pred, classes)
    matrix = {
        t: {p: sum(1 for r in rows if r["mapped"] == t and r["pred"] == p) for p in classes}
        for t in classes
    }
    return {
        "n": len(rows),
        "accuracy": round(float(correct.mean()), 4),
        "accuracy_ci95": bootstrap_ci(correct),
        "macro_f1_over_present_classes": round(
            float(np.mean([v["f1"] for k, v in pc.items() if v["support"]])), 4
        ),
        "ece_10_bins": round(expected_calibration_error(conf, correct), 4),
        "mean_confidence": round(float(conf.mean()), 4),
        "coverage_auto_accepted": round(float(accepted.mean()), 4),
        "accuracy_on_auto_accepted": round(float(correct[accepted].mean()), 4)
        if accepted.any()
        else None,
        "per_class": pc,
        "confusion_true_rows_pred_columns": matrix,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("dataset", choices=sorted(MAPPINGS))
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument(
        "--artifact", type=Path, default=Path("ml/artifacts/waste_classification/1.0.0")
    )
    ap.add_argument("--backbones", type=Path, default=Path("ml/artifacts/_backbones"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--reference-hashes",
        type=Path,
        help="JSON list of sha256 of images the model was trained on, to report exact overlap",
    )
    ap.add_argument("--limit", type=int, default=0, help="debug only: use the first N files")
    args = ap.parse_args(argv)
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; refusing to overwrite a recorded result")

    mapping = MAPPINGS[args.dataset]
    files = collect(args.root, mapping)
    if args.limit:
        files = files[: args.limit]
    model = WasteClassifier.load(args.artifact, args.backbones)
    classes = list(model.classes)
    train_hashes = (
        set(json.loads(args.reference_hashes.read_text())) if args.reference_hashes else set()
    )

    rows: list[dict[str, Any]] = []
    undecodable: list[str] = []
    seen: Counter[str] = Counter()
    overlap = 0
    start = time.perf_counter()
    for i, (folder, path) in enumerate(files):
        data = path.read_bytes()
        digest = sha256_bytes(data)
        seen[digest] += 1
        overlap += digest in train_hashes
        try:
            image: Image.Image = load_rgb_image(data)
        except Exception as exc:
            undecodable.append(f"{path.name}: {type(exc).__name__}")
            continue
        p = model.predict_images([image])[0]
        rows.append(
            {
                "folder": folder,
                "mapped": mapping[folder],
                "pred": p.label,
                "conf": p.confidence,
                "review": p.needs_review,
                "reasons": p.review_reasons,
                "novelty": p.novelty_similarity,
            }
        )
        if (i + 1) % 500 == 0:
            print(f"{i + 1}/{len(files)}", file=sys.stderr, flush=True)

    in_scope = [r for r in rows if r["mapped"] is not None]
    approx = APPROXIMATE.get(args.dataset, set())
    strict = [r for r in in_scope if r["folder"] not in approx]
    out_scope = [r for r in rows if r["mapped"] is None]
    result = {
        "dataset": args.dataset,
        "model": {
            "name": model.manifest["name"],
            "version": model.manifest["version"],
            "classes": classes,
        },
        "images_found": len(files),
        "images_decoded": len(rows),
        "undecodable": undecodable,
        "exact_duplicate_files_within_dataset": sum(c - 1 for c in seen.values() if c > 1),
        "exact_overlap_with_training_images": overlap if train_hashes else "not checked",
        "mapping": mapping,
        "approximate_mapping": sorted(approx),
        "files_listing_sha256": sha256_bytes(
            "\n".join(f"{p.parent.name}/{p.name}" for _, p in files).encode()
        ),
        "in_scope_without_approximate": summarise(strict, [c for c in classes if c != "trash"]),
        "in_scope_with_approximate": summarise(in_scope, classes),
        "out_of_scope": {
            "n": len(out_scope),
            "by_folder": {
                f: {
                    "n": sum(1 for r in out_scope if r["folder"] == f),
                    "sent_to_review": round(
                        sum(1 for r in out_scope if r["folder"] == f and r["review"])
                        / max(1, sum(1 for r in out_scope if r["folder"] == f)),
                        4,
                    ),
                    "predicted_as": dict(Counter(r["pred"] for r in out_scope if r["folder"] == f)),
                }
                for f in sorted({r["folder"] for r in out_scope})
            },
            "overall_sent_to_review": round(
                sum(1 for r in out_scope if r["review"]) / max(1, len(out_scope)), 4
            ),
            "note": (
                "The model has no class for these; a safe model sends them to a person. "
                "'Predicted as' is what it would say otherwise."
            ),
        },
        "review_reasons_all_images": dict(Counter(x for r in rows for x in r["reasons"])),
        "seconds": round(time.perf_counter() - start, 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("images_decoded", "undecodable")}, indent=2))
    for key in ("in_scope_without_approximate", "in_scope_with_approximate"):
        s = result[key]
        print(
            key,
            s["n"],
            "acc",
            s["accuracy"],
            s["accuracy_ci95"],
            "macroF1",
            s["macro_f1_over_present_classes"],
            "cov",
            s["coverage_auto_accepted"],
            "acc_accepted",
            s["accuracy_on_auto_accepted"],
        )
    print("out_of_scope sent to review:", result["out_of_scope"]["overall_sent_to_review"])


if __name__ == "__main__":
    main()
