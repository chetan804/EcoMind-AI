"""Bounded multi-dataset experiment: does adding real facility photos (RealWaste) help?

EXPERIMENT ONLY. RealWaste is CC BY-NC-SA 4.0, so no model trained on it may be released or
activated in this project. The experiment quantifies what a legitimately licensed real-world
dataset would be worth, to justify the dataset search; it writes no model artifact.

Design (all choices made before any test number was seen):
* Frozen backbones from the released pipeline (identity view only; no augmentation, no TTA).
* Head: multinomial logistic regression on L2-normalised features x10 (as the released model).
* Taxonomy of the experiment (8 classes): cardboard, glass, metal, paper, plastic, trash, organic,
  textile. RealWaste "Food Organics" + "Vegetation" -> organic; "Textile Trash" -> textile;
  "Miscellaneous Trash" -> trash (approximate). TrashNet has no organic/textile images.
* Splits are group-aware: near-duplicate images (cosine >= 0.70 on S embeddings, per class) never
  straddle train/validation/test. TrashNet uses the exact split of the released model
  (artifacts/split.json); RealWaste uses the same procedure (6 stratified group folds, fold 0 test,
  fold 1 validation).
* C (grid), temperature and the review rule are chosen on VALIDATION data only; test is read once.
* Training mixtures: TN (TrashNet only, 6 classes), RW (RealWaste only), TN+RW. Each is evaluated
  on TrashNet-test and RealWaste-test (cross-dataset when the mixture lacks that dataset).

    PYTHONPATH=. python -m ml.waste_classification.research.multi_dataset_experiment \\
        --out docs/ml/dataset-research/experiments/multi-dataset-realwaste.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression

from ml.common.evaluation import metrics as mt
from ml.waste_classification.data.trashnet import Sample, assign_folds, build_groups, list_samples
from ml.waste_classification.research.cross_dataset import MAPPINGS
from ml.waste_classification.training.features import REPO, backbone_embeddings, load_config
from ml.waste_classification.training.pipeline import choose_review_thresholds

CLASSES8 = ["cardboard", "glass", "metal", "paper", "plastic", "trash", "organic", "textile"]
RW_TO_8 = {
    **{k: v for k, v in MAPPINGS["realwaste"].items() if v},
    "Food Organics": "organic",
    "Vegetation": "organic",
    "Textile Trash": "textile",
}
SHARED6 = CLASSES8[:6]
INPUT_SCALE = 10.0
C_GRID = [0.01, 0.03, 0.1, 0.3]
Arr = NDArray[np.float64]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def fit(
    x: NDArray[np.float32], y: NDArray[np.int_], c: float, balanced: bool
) -> LogisticRegression:
    model = LogisticRegression(C=c, class_weight="balanced" if balanced else None, max_iter=2000)
    model.fit(x * INPUT_SCALE, y)
    return model


def scores(model: LogisticRegression, x: NDArray[np.float32], n_classes: int) -> Arr:
    """Linear scores widened to ``n_classes`` columns (absent classes get a very low score)."""
    raw = np.asarray(model.decision_function(x * INPUT_SCALE), dtype=np.float64)
    full = np.full((len(x), n_classes), -50.0)
    full[:, model.classes_] = raw
    return full


def evaluate(
    y: NDArray[np.int_],
    proba: Arr,
    novelty: Arr,
    rule: dict[str, Any],
    groups: NDArray[np.int_],
    seed: int,
) -> dict[str, Any]:
    present = np.unique(y)
    pred = proba.argmax(axis=1)
    conf = proba.max(axis=1)
    accepted = (conf >= rule["min_confidence"]) & (novelty >= rule["min_novelty_similarity"])
    correct = pred == y
    n = len(CLASSES8)

    def f1(i: NDArray[np.int_]) -> float:
        reports = mt.per_class_report(mt.confusion_matrix(y[i], pred[i], n))
        return float(np.mean([reports[k].f1 for k in present]))

    acc_ci = mt.grouped_bootstrap(
        lambda i: mt.accuracy(y[i], pred[i]), groups, resamples=1000, confidence=0.95, seed=seed
    )
    f1_ci = mt.grouped_bootstrap(f1, groups, resamples=1000, confidence=0.95, seed=seed)
    ece, _ = mt.expected_calibration_error(y, proba)
    reports = mt.per_class_report(mt.confusion_matrix(y, pred, n))
    return {
        "n": len(y),
        "accuracy": round(mt.accuracy(y, pred), 4),
        "accuracy_ci95": [round(acc_ci[0], 4), round(acc_ci[1], 4)],
        "macro_f1_present_classes": round(f1(np.arange(len(y))), 4),
        "macro_f1_ci95": [round(f1_ci[0], 4), round(f1_ci[1], 4)],
        "ece": round(float(ece), 4),
        "coverage_auto_accepted": round(float(accepted.mean()), 4),
        "accuracy_on_auto_accepted": round(float(correct[accepted].mean()), 4)
        if accepted.any()
        else None,
        "per_class_f1": {CLASSES8[k]: round(reports[k].f1, 4) for k in present},
        "per_class_support": {CLASSES8[k]: int(reports[k].support) for k in present},
    }


@dataclass
class Pool:
    """One dataset's features, labels, duplicate-group ids and split indices."""

    x: NDArray[np.float32]
    y: NDArray[np.int_]
    group: NDArray[np.int_]
    split: dict[str, NDArray[np.int_]]

    def take(self, name: str) -> tuple[NDArray[np.float32], NDArray[np.int_], NDArray[np.int_]]:
        idx = self.split[name]
        return self.x[idx], self.y[idx], self.group[idx]


def run_mixture(
    pools: dict[str, Pool], parts: list[str], balanced: bool, config: dict[str, Any]
) -> dict[str, Any]:
    """Fit on the train splits of ``parts``; choose C, temperature and review rule on their
    validation splits; read the two test splits once."""
    seed = int(config["seed"])
    n_classes = len(CLASSES8)
    x_tr = np.concatenate([pools[p].take("train")[0] for p in parts])
    y_tr = np.concatenate([pools[p].take("train")[1] for p in parts])
    x_va = np.concatenate([pools[p].take("val")[0] for p in parts])
    y_va = np.concatenate([pools[p].take("val")[1] for p in parts])
    best_c, best_f1, best_model = C_GRID[0], -1.0, None
    for c in C_GRID:  # validation macro-F1 only
        model = fit(x_tr, y_tr, c, balanced)
        val_pred = scores(model, x_va, n_classes).argmax(axis=1)
        val_f1 = mt.macro_f1(y_va, val_pred, n_classes)
        if val_f1 > best_f1 + 1e-9:
            best_c, best_f1, best_model = c, val_f1, model
    if best_model is None:
        raise RuntimeError("no head could be fitted")
    head = best_model
    cols = head.classes_
    temperature = float(
        mt.fit_temperature(np.searchsorted(cols, y_va), scores(head, x_va, n_classes)[:, cols])
    )

    def proba_of(x: NDArray[np.float32]) -> Arr:
        return mt.softmax(scores(head, x, n_classes), temperature)

    nov_va = (x_va @ x_tr.T).max(axis=1)
    rule = choose_review_thresholds(
        y_va,
        proba_of(x_va),
        nov_va,
        target_precision=config["review"]["target_precision"],
        novelty_quantile=config["review"]["novelty_quantile"],
    )
    test: dict[str, Any] = {}
    shared_ids = [CLASSES8.index(c) for c in SHARED6]
    for name in ("TN", "RW"):
        xt, yt, gt = pools[name].take("test")
        nov = (xt @ x_tr.T).max(axis=1)
        p = proba_of(xt)
        shared = np.isin(yt, shared_ids)  # the six classes every mixture can predict
        test[f"{name}_shared6"] = evaluate(
            yt[shared], p[shared], nov[shared], rule, gt[shared], seed
        )
        if name == "RW":
            if len(cols) == n_classes:
                test["RW_all8"] = evaluate(yt, p, nov, rule, gt, seed)
            other = ~shared  # organic + textile images
            accepted = (p[other].max(axis=1) >= rule["min_confidence"]) & (
                nov[other] >= rule["min_novelty_similarity"]
            )
            test["RW_organic_textile_auto_accepted_share"] = round(float(accepted.mean()), 4)
            test["RW_organic_textile_n"] = int(other.sum())
    return {
        "train_images": len(y_tr),
        "validation_images": len(y_va),
        "C": best_c,
        "temperature": round(temperature, 4),
        "class_weight": "balanced" if balanced else "none",
        "review_rule": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in rule.items()},
        "classes_in_training": [CLASSES8[k] for k in cols],
        "val_macro_f1": round(best_f1, 4),
        "test": test,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--realwaste-root", type=Path, default=REPO / "datasets/external/realwaste-src/RealWaste"
    )
    ap.add_argument("--backbones", default="S,M,L")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; refusing to overwrite a recorded result")
    config = load_config()
    seed = int(config["seed"])

    # ---- data -------------------------------------------------------------------------------
    tn = list_samples(
        REPO / "datasets/external/trashnet/dataset-resized", config["dataset"]["classes"]
    )
    split = json.loads((REPO / "ml/artifacts/waste_classification/split.json").read_text())
    if split["keys"] != [s.key for s in tn]:
        raise SystemExit(
            "artifacts/split.json does not match the TrashNet file list; rerun training"
        )
    tn_fold, tn_group = np.array(split["fold"]), np.array(split["group"])
    tn_y = np.array([CLASSES8.index(s.label) for s in tn])

    rw: list[Sample] = []
    for folder in sorted(RW_TO_8):
        files = sorted(
            p
            for p in (args.realwaste_root / folder).iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        rw.extend(Sample(p, RW_TO_8[folder], CLASSES8.index(RW_TO_8[folder])) for p in files)
    rw_y = np.array([s.label_index for s in rw])
    log(f"TrashNet {len(tn)} images, RealWaste {len(rw)} images")

    def emb(name: str, samples: list[Sample], cached_full: bool) -> NDArray[np.float32]:
        variants = config["augmentations"] if cached_full else ["identity"]
        e = backbone_embeddings(config, name, samples, variants)[:, 0]
        return np.asarray(e / np.linalg.norm(e, axis=1, keepdims=True), dtype=np.float32)

    log("grouping RealWaste near-duplicates (S embeddings, same threshold as TrashNet)")
    rw_s = emb("S", rw, False)
    rw_group = build_groups(rw_s, rw_y, config["grouping"]["min_cosine_similarity"])
    rw_fold = assign_folds(rw_y, rw_group, n_folds=config["split"]["n_folds"], seed=seed)
    sp = config["split"]
    ds: dict[str, dict[str, NDArray[np.int_]]] = {}
    for name, fold, group in (("TN", tn_fold, tn_group), ("RW", rw_fold, rw_group)):
        te, va = fold == sp["test_fold"], fold == sp["validation_fold"]
        tr = ~(te | va)
        for a, b in ((tr, va), (tr, te), (va, te)):
            if set(group[a]) & set(group[b]):
                raise RuntimeError(f"{name}: a duplicate group straddles two splits")
        ds[name] = {
            "train": np.flatnonzero(tr),
            "val": np.flatnonzero(va),
            "test": np.flatnonzero(te),
        }

    audit = {
        "realwaste_groups": int(rw_group.max()) + 1,
        "realwaste_images_in_multi_image_groups": round(
            float((np.bincount(rw_group)[rw_group] > 1).mean()), 4
        ),
        "realwaste_largest_group": int(np.bincount(rw_group).max()),
        "split_sizes": {k: {s: len(v) for s, v in d.items()} for k, d in ds.items()},
        "realwaste_class_counts": {c: int((rw_y == i).sum()) for i, c in enumerate(CLASSES8)},
        "no_group_straddles_splits": True,
    }

    # ---- experiments -----------------------------------------------------------------------------
    results: dict[str, Any] = {}
    mixtures = {"TN": ["TN"], "RW": ["RW"], "TN+RW": ["TN", "RW"]}
    for backbone in args.backbones.split(","):
        log(f"backbone {backbone}")
        pools = {
            "TN": Pool(emb(backbone, tn, True), tn_y, tn_group, ds["TN"]),
            "RW": Pool(
                emb(backbone, rw, False), rw_y, rw_group + int(tn_group.max()) + 1, ds["RW"]
            ),
        }
        for mix_name, parts in mixtures.items():
            for balanced in (True, False):
                if backbone != "M" and not balanced:
                    continue  # the balancing ablation is run on one backbone only
                entry = run_mixture(pools, parts, balanced, config)
                key = f"{backbone}|{mix_name}|{'balanced' if balanced else 'unbalanced'}"
                results[key] = entry
                t = entry["test"]
                log(
                    f"{key}: C={entry['C']} TN6 acc={t['TN_shared6']['accuracy']} "
                    f"RW6 acc={t['RW_shared6']['accuracy']}"
                )

    out = {
        "experiment_only": True,
        "licence_note": (
            "RealWaste is CC BY-NC-SA 4.0: no model trained on it is released or activated."
        ),
        "taxonomy": CLASSES8,
        "realwaste_mapping": RW_TO_8,
        "audit": audit,
        "seed": seed,
        "c_grid": C_GRID,
        "config_sha256": hashlib.sha256(
            (REPO / "ml/configs/waste_classification.yaml").read_bytes()
        ).hexdigest(),
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    log(f"wrote {args.out}")


if __name__ == "__main__":
    main()
