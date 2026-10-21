"""Bounded experiment: what would TrashBox add to the material classifier? (RESEARCH ONLY)

STATUS OF THE DATA. TrashBox (github.com/nikhilvenkatkumsetty/TrashBox) has no licence in its
repository. The project owner reports (2026-10-21) that the authors gave verbal permission by
telephone; nothing is in writing. This experiment therefore treats TrashBox as research input only:
it writes NO model artifact, registers nothing and activates nothing. No model trained on it may be
released until written permission and licence terms are on file
(docs/project-completion/DECISION_LOG.md).
RealWaste (CC BY-NC-SA 4.0) is used here only as an external TEST set (never trained on).

Design, fixed before any number was seen:
* Taxonomy, 8 classes: the six TrashNet classes plus ``e_waste`` and ``medical`` (TrashBox's two
  extra classes). TrashBox has no ``trash`` class; TrashNet has no e_waste or medical.
* TrashBox: only the ``TrashBox_train_set`` tree (the sub-folder tree duplicates it), at most
  ``--per-class`` images per class by a seeded shuffle of the sorted file list (compute bound).
  Exact duplicates (SHA-256) inside TrashBox and against TrashNet/RealWaste are counted and dropped
  from TrashBox before splitting.
* Frozen backbone of the released model (EfficientNet-EdgeTPU-M), identity view, L2-normalised
  features, multinomial logistic regression x10 input scale, as the released pipeline. S embeddings
  group near-duplicates (same threshold as TrashNet); a duplicate group never straddles splits.
* TrashNet uses the exact split of the released model (artifacts/split.json). TrashBox uses the same
  procedure (6 stratified group folds, fold 0 test, fold 1 validation).
* C (grid), temperature and the review rule are chosen on VALIDATION data of the training mixture
  only; every test set is read once. Mixtures: TN, TB, TN+TB, all class-balanced.
* Test sets: TrashNet-test, TrashBox-test, and (when present) RealWaste's five shared material
  classes as a purely external set. Metrics are reported on the classes both sides share (five
  materials) and, for TrashBox, on all seven of its classes.

    PYTHONPATH=. python -m ml.waste_classification.research.trashbox_experiment \\
        --trashbox-root datasets/external/trashbox-src/TrashBox_train_set \\
        --out docs/ml/dataset-research/experiments/trashbox-experiment.json
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
from ml.common.preprocessing.images import InvalidImageError, load_rgb_image
from ml.waste_classification.data.trashnet import Sample, assign_folds, build_groups, list_samples
from ml.waste_classification.research.cross_dataset import MAPPINGS
from ml.waste_classification.training.features import REPO, backbone_embeddings, load_config
from ml.waste_classification.training.pipeline import choose_review_thresholds

CLASSES = ["cardboard", "glass", "metal", "paper", "plastic", "trash", "e_waste", "medical"]
SHARED5 = CLASSES[:5]
TB_FOLDERS = {
    "cardboard": "cardboard",
    "glass": "glass",
    "metal": "metal",
    "paper": "paper",
    "plastic": "plastic",
    "e-waste": "e_waste",
    "medical": "medical",
}
INPUT_SCALE = 10.0
C_GRID = [0.01, 0.03, 0.1, 0.3]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
# A TrashBox/RealWaste image this similar to an image of another dataset is a copy or re-photograph.
CROSS_DATASET_NEAR_DUPLICATE = 0.85
Arr = NDArray[np.float64]


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fit(x: NDArray[np.float32], y: NDArray[np.int_], c: float) -> LogisticRegression:
    model = LogisticRegression(C=c, class_weight="balanced", max_iter=2000)
    model.fit(x * INPUT_SCALE, y)
    return model


def scores(model: LogisticRegression, x: NDArray[np.float32]) -> Arr:
    raw = np.asarray(model.decision_function(x * INPUT_SCALE), dtype=np.float64)
    full = np.full((len(x), len(CLASSES)), -50.0)  # classes absent from training: very low score
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
    accepted = (proba.max(axis=1) >= rule["min_confidence"]) & (
        novelty >= rule["min_novelty_similarity"]
    )
    correct = pred == y
    n = len(CLASSES)

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
        "per_class_f1": {CLASSES[k]: round(reports[k].f1, 4) for k in present},
        "per_class_support": {CLASSES[k]: int(reports[k].support) for k in present},
    }


@dataclass
class Pool:
    x: NDArray[np.float32]
    y: NDArray[np.int_]
    group: NDArray[np.int_]
    split: dict[str, NDArray[np.int_]]

    def take(self, name: str) -> tuple[NDArray[np.float32], NDArray[np.int_], NDArray[np.int_]]:
        idx = self.split[name]
        return self.x[idx], self.y[idx], self.group[idx]


def run_mixture(
    pools: dict[str, Pool],
    parts: list[str],
    external: Pool | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    seed = int(config["seed"])
    x_tr = np.concatenate([pools[p].take("train")[0] for p in parts])
    y_tr = np.concatenate([pools[p].take("train")[1] for p in parts])
    x_va = np.concatenate([pools[p].take("val")[0] for p in parts])
    y_va = np.concatenate([pools[p].take("val")[1] for p in parts])
    best_c, best_f1, head = C_GRID[0], -1.0, None
    for c in C_GRID:  # validation macro-F1 only
        model = fit(x_tr, y_tr, c)
        val_f1 = mt.macro_f1(y_va, scores(model, x_va).argmax(axis=1), len(CLASSES))
        if val_f1 > best_f1 + 1e-9:
            best_c, best_f1, head = c, val_f1, model
    if head is None:
        raise RuntimeError("no head could be fitted")
    cols = head.classes_
    temperature = float(
        mt.fit_temperature(np.searchsorted(cols, y_va), scores(head, x_va)[:, cols])
    )

    def proba_of(x: NDArray[np.float32]) -> Arr:
        return mt.softmax(scores(head, x), temperature)

    rule = choose_review_thresholds(
        y_va,
        proba_of(x_va),
        (x_va @ x_tr.T).max(axis=1),
        target_precision=config["review"]["target_precision"],
        novelty_quantile=config["review"]["novelty_quantile"],
    )
    shared_ids = [CLASSES.index(c) for c in SHARED5]
    test: dict[str, Any] = {}
    targets: list[tuple[str, Pool, str]] = [
        ("TN", pools["TN"], "test"),
        ("TB", pools["TB"], "test"),
    ]
    for name, pool, split in targets:
        xt, yt, gt = pool.take(split)
        nov = (xt @ x_tr.T).max(axis=1)
        p = proba_of(xt)
        keep = np.isin(yt, shared_ids)
        test[f"{name}_shared5"] = evaluate(yt[keep], p[keep], nov[keep], rule, gt[keep], seed)
        if name == "TB" and len(cols) > 5:
            test["TB_all7"] = evaluate(yt, p, nov, rule, gt, seed)
    if external is not None:
        xe, ye, ge = external.x, external.y, external.group
        nov = (xe @ x_tr.T).max(axis=1)
        test["RW_external_shared5"] = evaluate(ye, proba_of(xe), nov, rule, ge, seed)
    return {
        "train_images": len(y_tr),
        "validation_images": len(y_va),
        "C": best_c,
        "temperature": round(temperature, 4),
        "review_rule": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in rule.items()},
        "classes_in_training": [CLASSES[k] for k in cols],
        "val_macro_f1": round(best_f1, 4),
        "test": test,
    }


def pick_trashbox(root: Path, per_class: int, seed: int) -> tuple[list[Sample], dict[str, Any]]:
    rng = np.random.default_rng(seed)
    chosen: list[Sample] = []
    audit: dict[str, Any] = {"available": {}, "selected": {}}
    for folder, label in TB_FOLDERS.items():
        files = sorted(p for p in (root / folder).iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
        audit["available"][label] = len(files)
        order = rng.permutation(len(files))[:per_class]
        picked = [files[i] for i in sorted(order)]
        audit["selected"][label] = len(picked)
        chosen.extend(Sample(p, label, CLASSES.index(label)) for p in picked)
    return chosen, audit


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--trashbox-root", type=Path, required=True)
    ap.add_argument(
        "--realwaste-root", type=Path, default=REPO / "datasets/external/realwaste-src/RealWaste"
    )
    ap.add_argument("--per-class", type=int, default=1000)
    ap.add_argument("--backbone", default="M")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; refusing to overwrite a recorded result")
    config = load_config()
    seed = int(config["seed"])

    tn = list_samples(
        REPO / "datasets/external/trashnet/dataset-resized", config["dataset"]["classes"]
    )
    split = json.loads((REPO / "ml/artifacts/waste_classification/split.json").read_text())
    if split["keys"] != [s.key for s in tn]:
        raise SystemExit(
            "artifacts/split.json does not match the TrashNet file list; rerun training"
        )
    tn_fold, tn_group = np.array(split["fold"]), np.array(split["group"])
    tn_y = np.array([CLASSES.index(s.label) for s in tn])

    tb, tb_audit = pick_trashbox(args.trashbox_root, args.per_class, seed)
    log(f"TrashBox sample: {len(tb)} images {tb_audit['selected']}")

    # Exact duplicates: inside TrashBox, and against TrashNet and RealWaste (dropped from TrashBox).
    tn_hashes = {sha256_path(s.path) for s in tn}
    rw_files: list[Sample] = []
    rw_map = {k: v for k, v in MAPPINGS["realwaste"].items() if v in SHARED5}
    if args.realwaste_root.exists():
        for folder, label in sorted(rw_map.items()):
            for p in sorted((args.realwaste_root / folder).iterdir()):
                if p.suffix.lower() in IMAGE_SUFFIXES and label:
                    rw_files.append(Sample(p, label, CLASSES.index(label)))
    rw_hashes = {sha256_path(s.path) for s in rw_files}
    seen: set[str] = set()
    kept: list[Sample] = []
    dup_within = dup_tn = dup_rw = 0
    undecodable: list[str] = []
    for s in tb:
        data = s.path.read_bytes()
        try:
            load_rgb_image(data)
        except InvalidImageError:
            undecodable.append(s.key)  # reported, not skipped silently
            continue
        h = hashlib.sha256(data).hexdigest()
        if h in seen:
            dup_within += 1
        elif h in tn_hashes:
            dup_tn += 1
        elif h in rw_hashes:
            dup_rw += 1
        else:
            seen.add(h)
            kept.append(s)
    tb = kept
    tb_y = np.array([s.label_index for s in tb])
    log(
        f"after exact-duplicate removal: {len(tb)} "
        f"(undecodable {len(undecodable)}, within {dup_within}, "
        f"TrashNet {dup_tn}, RealWaste {dup_rw})"
    )

    def emb(name: str, samples: list[Sample], full: bool) -> NDArray[np.float32]:
        variants = config["augmentations"] if full else ["identity"]
        e = backbone_embeddings(config, name, samples, variants)[:, 0]
        return np.asarray(e / np.linalg.norm(e, axis=1, keepdims=True), dtype=np.float32)

    log("grouping TrashBox near-duplicates (S embeddings, same threshold as TrashNet)")
    tb_s = emb("S", tb, False)
    tn_s = emb("S", tn, True)
    sim_tn = (tb_s @ tn_s.T).max(axis=1)
    near_dup_audit: dict[str, Any] = {
        "metric": "max cosine similarity of S embeddings, TrashBox image vs any TrashNet image",
        "images_at_or_above": {str(t): int((sim_tn >= t).sum()) for t in (0.70, 0.80, 0.85, 0.90)},
        "dropped_threshold": CROSS_DATASET_NEAR_DUPLICATE,
    }
    keep = sim_tn < CROSS_DATASET_NEAR_DUPLICATE
    log(f"dropping {int((~keep).sum())} TrashBox images that nearly duplicate a TrashNet image")
    tb = [s for s, k in zip(tb, keep, strict=True) if k]
    tb_s = tb_s[keep]
    tb_y = np.array([s.label_index for s in tb])
    tb_group = build_groups(tb_s, tb_y, config["grouping"]["min_cosine_similarity"])
    tb_fold = assign_folds(tb_y, tb_group, n_folds=config["split"]["n_folds"], seed=seed)
    sp = config["split"]
    ds: dict[str, dict[str, NDArray[np.int_]]] = {}
    for name, fold, group in (("TN", tn_fold, tn_group), ("TB", tb_fold, tb_group)):
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

    rw_pool_inputs: tuple[list[Sample], NDArray[np.int_]] | None = None
    if rw_files:
        rw_y = np.array([s.label_index for s in rw_files])
        rw_s = emb("S", rw_files, False)
        sim_rw = np.maximum((rw_s @ tn_s.T).max(axis=1), (rw_s @ tb_s.T).max(axis=1))
        near_dup_audit["realwaste_images_at_or_above"] = {
            str(t): int((sim_rw >= t).sum()) for t in (0.70, 0.80, 0.85, 0.90)
        }
        rw_keep = sim_rw < CROSS_DATASET_NEAR_DUPLICATE
        rw_files = [s for s, k in zip(rw_files, rw_keep, strict=True) if k]
        rw_s = rw_s[rw_keep]
        rw_y = np.array([s.label_index for s in rw_files])
        rw_pool_inputs = (
            rw_files,
            build_groups(rw_s, rw_y, config["grouping"]["min_cosine_similarity"]),
        )
        log(f"RealWaste external set: {len(rw_files)} images in the five shared classes")

    backbone = args.backbone
    pools = {
        "TN": Pool(emb(backbone, tn, True), tn_y, tn_group, ds["TN"]),
        "TB": Pool(emb(backbone, tb, False), tb_y, tb_group + int(tn_group.max()) + 1, ds["TB"]),
    }
    external: Pool | None = None
    if rw_pool_inputs is not None:
        samples, groups = rw_pool_inputs
        external = Pool(
            emb(backbone, samples, False),
            np.array([s.label_index for s in samples]),
            groups + int(pools["TB"].group.max()) + 1,
            {},
        )

    results: dict[str, Any] = {}
    for mix_name, parts in {"TN": ["TN"], "TB": ["TB"], "TN+TB": ["TN", "TB"]}.items():
        entry = run_mixture(pools, parts, external, config)
        results[f"{backbone}|{mix_name}"] = entry
        t = entry["test"]
        log(
            f"{mix_name}: C={entry['C']} TN5 acc={t['TN_shared5']['accuracy']} "
            f"TB5 acc={t['TB_shared5']['accuracy']}"
            + (
                f" RW5 acc={t['RW_external_shared5']['accuracy']}"
                if "RW_external_shared5" in t
                else ""
            )
        )

    out = {
        "experiment_only": True,
        "licence_note": (
            "TrashBox: no licence in the repository; verbal permission reported by the owner, "
            "nothing in writing. RealWaste (external test only): CC BY-NC-SA 4.0. "
            "No model from this experiment is released, registered or activated."
        ),
        "taxonomy": CLASSES,
        "per_class_cap": args.per_class,
        "trashbox_audit": {
            **tb_audit,
            "exact_duplicates_dropped": {
                "within_trashbox": dup_within,
                "against_trashnet": dup_tn,
                "against_realwaste": dup_rw,
            },
            "undecodable_dropped": undecodable,
            "near_duplicates_vs_other_datasets": near_dup_audit,
            "images_used": len(tb),
            "groups": int(tb_group.max()) + 1,
            "largest_group": int(np.bincount(tb_group).max()),
            "split_sizes": {k: {s: len(v) for s, v in d.items()} for k, d in ds.items()},
        },
        "realwaste_external_images": len(rw_files),
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
