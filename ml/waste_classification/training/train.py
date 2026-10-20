"""Train, calibrate and evaluate the waste *material* classifier end to end.

    python -m ml.waste_classification.data.fetch          # once: pinned data + backbones
    python -m ml.waste_classification.training.train      # writes artifact, registry manifest, report

Order of decisions (nothing later may influence anything earlier):
  1  groups + split, fixed before modelling
  2  baselines + diagnostics
  3  model selection (TRAIN, grouped CV)
  4  temperature + review rule (VALIDATION)
  5  test evaluation (TEST, exactly once)
  6  robustness / OOD / latency (through the real inference code)
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from typing import Any

import numpy as np
import sklearn
import yaml
from numpy.typing import NDArray
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import SVC

from ml.common.evaluation import metrics as mt
from ml.common.preprocessing.images import load_rgb_image
from ml.waste_classification.data.trashnet import (
    assign_folds,
    build_groups,
    files_digest,
    list_samples,
)
from ml.waste_classification.evaluation.robustness import PERTURBATIONS
from ml.waste_classification.inference.classifier import INPUT_SCALE, WasteClassifier
from ml.waste_classification.inference.embedder import sha256_file
from ml.waste_classification.training import pipeline as pl
from ml.waste_classification.training.features import (
    BACKBONES,
    REPO,
    backbone_embeddings,
    embedder_for,
    handcrafted_features,
    load_config,
)

Ints = NDArray[np.int_]
CONFIG_PATH = REPO / "ml" / "configs" / "waste_classification.yaml"
_test_evaluations = 0


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def unit_concat(config: dict[str, Any], names: list[str], samples: list[Any]) -> Any:
    parts = []
    for name in names:
        emb = backbone_embeddings(config, name, samples, config["augmentations"])
        parts.append(emb / np.linalg.norm(emb, axis=-1, keepdims=True))
    return (np.concatenate(parts, axis=-1) / np.sqrt(len(names))).astype(np.float32)


def embed_latency_ms(config: dict[str, Any], names: list[str], samples: list[Any]) -> float:
    """p95 milliseconds for ONE forward pass over all backbones of a candidate (incl. resize)."""
    images = [load_rgb_image(s.path.read_bytes()) for s in samples[:: len(samples) // 40][:40]]
    total = 0.0
    for name in names:
        embedder = embedder_for(config, name)
        embedder.embed(images[:2])
        times = []
        for image in images:
            start = time.perf_counter()
            embedder.embed([image])
            times.append((time.perf_counter() - start) * 1000)
        total += float(np.percentile(times, 95))
    return total


def git_state() -> tuple[str, bool]:
    """(HEAD commit, whether the training-relevant code tree is clean at that commit)."""
    code_paths = ["ml/common", "ml/waste_classification", "ml/configs", "datasets/manifests"]
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(  # noqa: S603
            ["git", "status", "--porcelain", "--", *code_paths],  # noqa: S607
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        # `git status` does not list ignored files, but an ignored .py file used by the run would be
        # code that is missing from the recorded commit, so it counts as "not clean" too.
        hidden = subprocess.run(  # noqa: S603
            ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "--", *code_paths],  # noqa: S607
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        return head, not dirty and not [path for path in hidden if path.endswith(".py")]
    except (OSError, subprocess.CalledProcessError):
        return "unknown", False


def main() -> int:
    global _test_evaluations
    config = load_config(CONFIG_PATH)
    seed = config["seed"]
    classes: list[str] = config["dataset"]["classes"]
    root = REPO / "datasets" / "external" / "trashnet" / "dataset-resized"
    samples = list_samples(root, classes)
    y: Ints = np.array([s.label_index for s in samples])
    report: dict[str, Any] = {"classes": classes, "seed": seed}

    # ---- 1. groups + split -------------------------------------------------------------------
    log("1. grouping near-duplicates and fixing the split")
    grouping_emb = backbone_embeddings(
        config, config["grouping"]["backbone"], samples, config["augmentations"]
    )
    groups = build_groups(grouping_emb[:, 0], y, config["grouping"]["min_cosine_similarity"])
    folds = assign_folds(y, groups, n_folds=config["split"]["n_folds"], seed=seed)
    test_idx = np.flatnonzero(folds == config["split"]["test_fold"])
    val_idx = np.flatnonzero(folds == config["split"]["validation_fold"])
    train_idx = np.flatnonzero(
        ~np.isin(folds, [config["split"]["test_fold"], config["split"]["validation_fold"]])
    )
    for a, b in ((train_idx, val_idx), (train_idx, test_idx), (val_idx, test_idx)):
        if set(groups[a]) & set(groups[b]):
            raise RuntimeError("a duplicate group straddles two splits")
    report["split"] = {
        "n_images": len(samples),
        "n_groups": int(groups.max() + 1),
        "largest_group": int(np.bincount(groups).max()),
        "images_in_multi_image_groups": float((np.bincount(groups)[groups] > 1).mean()),
        "sizes": {"train": len(train_idx), "validation": len(val_idx), "test": len(test_idx)},
        "class_counts": {
            name: {c: int((y[idx] == i).sum()) for i, c in enumerate(classes)}
            for name, idx in (("train", train_idx), ("validation", val_idx), ("test", test_idx))
        },
        "no_group_straddles_splits": True,
    }
    split_file = REPO / "ml" / "artifacts" / "waste_classification" / "split.json"
    split_file.parent.mkdir(parents=True, exist_ok=True)
    split_file.write_text(
        json.dumps(
            {"keys": [s.key for s in samples], "fold": folds.tolist(), "group": groups.tolist()}
        )
    )

    # ---- 2a. baselines (train CV + validation; test is evaluated once, later) -----------------
    log("2a. baselines")
    cv_folds = pl.grouped_folds(y, groups, train_idx, config["selection"]["cv_folds"], seed)
    majority = int(np.bincount(y[train_idx]).argmax())
    hand = handcrafted_features(samples)
    hand_cv: dict[float, float] = {}
    for c_value in (0.01, 0.1, 1.0, 10.0):
        scores = []
        for fit_i, held_i in cv_folds:
            mu, sd = hand[fit_i].mean(0), hand[fit_i].std(0) + 1e-6
            m = LogisticRegression(C=c_value, class_weight="balanced", max_iter=3000).fit(
                (hand[fit_i] - mu) / sd, y[fit_i]
            )
            scores.append(mt.macro_f1(y[held_i], m.predict((hand[held_i] - mu) / sd), 6))
        hand_cv[c_value] = float(np.mean(scores))
    hand_c = max(hand_cv, key=lambda c: hand_cv[c])
    mu_h, sd_h = hand[train_idx].mean(0), hand[train_idx].std(0) + 1e-6
    hand_model = LogisticRegression(C=hand_c, class_weight="balanced", max_iter=3000).fit(
        (hand[train_idx] - mu_h) / sd_h, y[train_idx]
    )
    report["baselines"] = {
        "majority_class": {
            "class": classes[majority],
            "val_macro_f1": mt.macro_f1(y[val_idx], np.full(len(val_idx), majority), 6),
        },
        "handcrafted_logreg": {
            "features": "4x4x4 HSV histogram + 8-bin gradient orientation + 3 intensity statistics",
            "cv_macro_f1_by_C": {str(k): v for k, v in hand_cv.items()},
            "chosen_C": hand_c,
            "cv_macro_f1": hand_cv[hand_c],
            "val_macro_f1": mt.macro_f1(
                y[val_idx], hand_model.predict((hand[val_idx] - mu_h) / sd_h), 6
            ),
        },
    }

    # ---- 3. model selection on TRAIN only (grouped CV) ----------------------------------------
    log("3. model selection (train-only grouped CV)")
    sel = config["selection"]
    tta_idx = {
        k: [config["augmentations"].index(v) for v in vs]
        for k, vs in config["tta_candidates"].items()
    }
    features: dict[str, Any] = {}
    cv_table: dict[str, dict[float, pl.CVResult]] = {}
    chosen_c: dict[str, float] = {}
    latency: dict[str, float] = {}
    for cand in sel["candidates"]:
        names = cand.split("+")
        features[cand] = unit_concat(config, names, samples)
        latency[cand] = embed_latency_ms(config, names, samples)
        cv_table[cand] = {}
        for c_value in sel["c_grid"]:
            cv_table[cand][c_value] = pl.cross_validate(features[cand], y, cv_folds, c_value)
            r = cv_table[cand][c_value]
            log(
                f"   {cand:4s} C={c_value:<6} cvF1={r.mean('f1'):.4f} trainF1={r.mean('train_f1'):.4f}"
            )
        chosen_c[cand] = pl.one_se_choice(sel["c_grid"], cv_table[cand])
    pairs = []
    for cand in sel["candidates"]:
        r = cv_table[cand][chosen_c[cand]]
        for tta, idx in tta_idx.items():
            p95 = latency[cand] * len(idx)
            mean_f1, sem = pl.tta_cv_f1(r, y, idx)
            pairs.append(
                {
                    "candidate": cand,
                    "tta": tta,
                    "passes": len(idx),
                    "C": chosen_c[cand],
                    "cv_macro_f1": mean_f1,
                    "cv_sem": sem,
                    "p95_ms_estimate": p95,
                    "feasible": p95 <= sel["max_p95_latency_ms"],
                }
            )
    feasible = [p for p in pairs if p["feasible"]]
    best = max(feasible, key=lambda p: p["cv_macro_f1"])
    within = [p for p in feasible if p["cv_macro_f1"] >= best["cv_macro_f1"] - best["cv_sem"]]
    chosen = min(within, key=lambda p: (p["p95_ms_estimate"], p["passes"], -p["cv_macro_f1"]))
    cand, c_final, variant_idx = chosen["candidate"], chosen["C"], tta_idx[chosen["tta"]]
    cv_chosen = cv_table[cand][c_final]
    log(f"   selected {cand} C={c_final} TTA={chosen['tta']} cvF1={chosen['cv_macro_f1']:.4f}")
    report["selection"] = {
        "rule": "best CV macro-F1 among latency-feasible (candidate, TTA); then the cheapest within 1 SE; C by the 1-SE rule",
        "latency_p95_ms_per_pass": latency,
        "cv_by_candidate_and_C": {
            k: {
                str(c): {
                    "cv_macro_f1": r.mean("f1"),
                    "cv_sem": r.sem("f1"),
                    "cv_accuracy": r.mean("acc"),
                    "cv_log_loss": r.mean("nll"),
                    "train_macro_f1": r.mean("train_f1"),
                }
                for c, r in v.items()
            }
            for k, v in cv_table.items()
        },
        "chosen_C_per_candidate": chosen_c,
        "candidate_tta_pairs": pairs,
        "chosen": chosen,
    }

    # ---- 2b. diagnostics on the chosen configuration (train data only) -------------------------
    log("2b. diagnostics (augmentation ablation, capacity probe, learning curve)")
    x = features[cand]
    no_aug = pl.cross_validate(x, y, cv_folds, c_final, augment=False)
    svc_scores = []
    for fit_i, held_i in cv_folds:
        svc = SVC(C=10, gamma="scale", class_weight="balanced").fit(
            x[fit_i, 0] * INPUT_SCALE, y[fit_i]
        )
        svc_scores.append(mt.macro_f1(y[held_i], svc.predict(x[held_i, 0] * INPUT_SCALE), 6))
    rng = np.random.default_rng(seed)
    curve = []
    for frac in (0.1, 0.2, 0.4, 0.6, 0.8, 1.0):
        held_f1, own_f1 = [], []
        for fit_i, held_i in cv_folds:
            ug = np.unique(groups[fit_i])
            keep = rng.choice(ug, size=max(int(len(ug) * frac), 6), replace=False)
            sub = fit_i[np.isin(groups[fit_i], keep)]
            model = pl.fit_head(x[sub], y[sub], c_final)
            held_f1.append(
                mt.macro_f1(y[held_i], pl.head_scores(model, x[held_i][:, :1])[:, 0].argmax(1), 6)
            )
            own_f1.append(
                mt.macro_f1(y[sub], pl.head_scores(model, x[sub][:, :1])[:, 0].argmax(1), 6)
            )
        curve.append(
            {
                "train_fraction": frac,
                "n_train_images": int(len(train_idx) * frac * 0.8),
                "cv_macro_f1": float(np.mean(held_f1)),
                "train_macro_f1": float(np.mean(own_f1)),
            }
        )
    # leakage study: the same recipe under a naive random (group-ignoring) split
    naive = StratifiedKFold(config["split"]["n_folds"], shuffle=True, random_state=seed)
    naive_folds = np.zeros(len(y), dtype=int)
    for k, (_, held) in enumerate(naive.split(np.zeros(len(y)), y)):
        naive_folds[held] = k
    n_test = np.flatnonzero(naive_folds == 0)
    n_train = np.flatnonzero(~np.isin(naive_folds, [0, 1]))
    naive_model = pl.fit_head(x[n_train], y[n_train], c_final)
    naive_pred = pl.tta_logits(pl.head_scores(naive_model, x[n_test]), variant_idx).argmax(1)
    g_unit = grouping_emb[:, 0] / np.linalg.norm(grouping_emb[:, 0], axis=1, keepdims=True)

    def twin_share(train_i: Ints, test_i: Ints) -> float:
        same = y[test_i][:, None] == y[train_i][None, :]
        sim = np.where(same, g_unit[test_i] @ g_unit[train_i].T, -1).max(axis=1)
        return float((sim >= 0.80).mean())

    report["diagnostics"] = {
        "chosen_cv": {
            "cv_macro_f1": cv_chosen.mean("f1"),
            "cv_accuracy": cv_chosen.mean("acc"),
            "cv_folds_macro_f1": cv_chosen.f1,
            "train_macro_f1": cv_chosen.mean("train_f1"),
            "train_minus_cv_gap": cv_chosen.mean("train_f1") - cv_chosen.mean("f1"),
        },
        "augmentation_ablation": {
            "with_augmentation_cv_macro_f1": cv_chosen.mean("f1"),
            "without_augmentation_cv_macro_f1": no_aug.mean("f1"),
        },
        "capacity_probe": {
            "linear_head_cv_macro_f1": no_aug.mean("f1"),
            "rbf_svm_cv_macro_f1": float(np.mean(svc_scores)),
            "note": "same features, no augmentation; compares a linear head with a more flexible non-linear one",
        },
        "learning_curve": curve,
        "leakage_study": {
            "naive_random_split_macro_f1": mt.macro_f1(y[n_test], naive_pred, 6),
            "naive_random_split_accuracy": mt.accuracy(y[n_test], naive_pred),
            "share_of_test_images_with_a_near_twin_in_train_naive": twin_share(n_train, n_test),
            "share_of_test_images_with_a_near_twin_in_train_grouped": twin_share(
                train_idx, test_idx
            ),
            "near_twin_definition": "same class, cosine similarity >= 0.80 (S backbone)",
        },
    }

    # ---- 4. fit on train; temperature + review rule on VALIDATION ------------------------------
    log("4. final fit, temperature scaling, review rule")
    model = pl.fit_head(x[train_idx], y[train_idx], c_final)
    scores_all = pl.head_scores(model, x)
    logits = pl.tta_logits(scores_all, variant_idx)
    temperature = mt.fit_temperature(y[val_idx], logits[val_idx])
    reference = (x[train_idx, 0]).astype(np.float16)
    ref32 = reference.astype(np.float32)
    novelty_all = (x[:, 0] @ ref32.T).max(axis=1)
    # train images are in the reference set, so only val/test novelty is meaningful
    proba_val = mt.softmax(logits[val_idx], temperature)
    rule = pl.choose_review_thresholds(
        y[val_idx],
        proba_val,
        novelty_all[val_idx],
        target_precision=config["review"]["target_precision"],
        novelty_quantile=config["review"]["novelty_quantile"],
    )
    report["calibration"] = {
        "method": "temperature scaling on validation",
        "temperature": temperature,
    }
    report["review_rule"] = rule
    val_eval = pl.evaluate_probabilities(y[val_idx], proba_val, groups[val_idx], config, seed)
    val_raw = pl.evaluate_probabilities(y[val_idx], mt.softmax(logits[val_idx]), None, config, seed)
    report["validation"] = {
        "calibrated": val_eval,
        "uncalibrated_ece": val_raw["ece"],
        "uncalibrated_log_loss": val_raw["log_loss"],
        "uncalibrated_mean_confidence": val_raw["mean_confidence"],
        "review": pl.review_outcome(y[val_idx], proba_val, novelty_all[val_idx], rule),
        "handcrafted_macro_f1": report["baselines"]["handcrafted_logreg"]["val_macro_f1"],
    }
    train_pred = logits[train_idx].argmax(1)
    report["train_in_sample"] = {
        "accuracy": mt.accuracy(y[train_idx], train_pred),
        "macro_f1": mt.macro_f1(y[train_idx], train_pred, 6),
    }

    # ---- 5. TEST: evaluated exactly once -------------------------------------------------------
    log("5. test evaluation (once)")
    _test_evaluations += 1
    if _test_evaluations != 1:
        raise RuntimeError("the test split must be evaluated exactly once")
    proba_test = mt.softmax(logits[test_idx], temperature)
    test_eval = pl.evaluate_probabilities(y[test_idx], proba_test, groups[test_idx], config, seed)
    test_raw = pl.evaluate_probabilities(
        y[test_idx], mt.softmax(logits[test_idx]), None, config, seed
    )
    hand_test_pred = hand_model.predict((hand[test_idx] - mu_h) / sd_h)
    report["test"] = {
        "calibrated": test_eval,
        "uncalibrated_ece": test_raw["ece"],
        "uncalibrated_log_loss": test_raw["log_loss"],
        "uncalibrated_mean_confidence": test_raw["mean_confidence"],
        "review": pl.review_outcome(y[test_idx], proba_test, novelty_all[test_idx], rule),
        "selective_curve": mt.selective_curve(
            y[test_idx], proba_test, [0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98]
        ),
        "baselines": {
            "majority_macro_f1": mt.macro_f1(y[test_idx], np.full(len(test_idx), majority), 6),
            "majority_accuracy": mt.accuracy(y[test_idx], np.full(len(test_idx), majority)),
            "handcrafted_macro_f1": mt.macro_f1(y[test_idx], hand_test_pred, 6),
            "handcrafted_accuracy": mt.accuracy(y[test_idx], hand_test_pred),
        },
        "margin_over_handcrafted_macro_f1": test_eval["macro_f1"]
        - mt.macro_f1(y[test_idx], hand_test_pred, 6),
        "required_margin": 0.10,
    }

    # ---- artifact ------------------------------------------------------------------------------
    version = config["version"]
    out_dir = REPO / "ml" / "artifacts" / "waste_classification" / version
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        out_dir / "head.npz",
        coef=model.coef_.astype(np.float32),
        intercept=model.intercept_.astype(np.float32),
    )
    np.save(out_dir / "novelty_reference.npy", reference)
    names = cand.split("+")
    trained_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "name": config["name"],
        "version": version,
        "task": "material_category",
        "classes": classes,
        "backbones": [
            {
                "name": n,
                "file": config["backbones"][n]["file"],
                "sha256": sha256_file(BACKBONES / config["backbones"][n]["file"]),
            }
            for n in names
        ],
        "tta_variants": [config["augmentations"][i] for i in variant_idx],
        "input_scale": INPUT_SCALE,
        "temperature": temperature,
        "review": {
            "min_confidence": rule["min_confidence"],
            "min_novelty_similarity": rule["min_novelty_similarity"],
        },
        "files": {n: sha256_file(out_dir / n) for n in ("head.npz", "novelty_reference.npy")},
        "material_category_codes": {
            c: c for c in classes
        },  # model class -> material_categories.code
        "trained_at_utc": trained_at,
        "evaluation": {
            "dataset": "TrashNet 1.0 (studio-style photographs; not a field accuracy)",
            "split": "group-aware test split, evaluated once",
            "n_test": test_eval["n"],
            "accuracy": test_eval["accuracy"],
            "accuracy_ci95": test_eval["accuracy_ci"],
            "macro_f1": test_eval["macro_f1"],
            "macro_f1_ci95": test_eval["macro_f1_ci"],
            "ece": test_eval["ece"],
            "auto_accept_rate": report["test"]["review"]["auto_accept_rate"],
            "auto_accepted_accuracy": report["test"]["review"]["accepted_accuracy"],
        },
    }
    (out_dir / "model.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))

    # ---- 6. real inference code: parity, robustness, OOD, latency ------------------------------
    log("6. parity / robustness / OOD / latency through WasteClassifier")
    clf = WasteClassifier.load(out_dir, BACKBONES)
    probe = test_idx[:: max(len(test_idx) // 25, 1)][:25]
    served = np.stack(
        [clf.logits(clf.features([load_rgb_image(samples[i].path.read_bytes())]))[0] for i in probe]
    )
    report["parity"] = {
        "n_images": len(probe),
        "max_abs_logit_difference": float(np.abs(served - logits[probe]).max()),
        "same_predictions": bool((served.argmax(1) == logits[probe].argmax(1)).all()),
    }
    if report["parity"]["max_abs_logit_difference"] >= 1e-3:
        raise RuntimeError("train/serve parity broken")

    def stress(transform: Any) -> dict[str, float]:
        gen = np.random.default_rng(seed)
        imgs = [transform(load_rgb_image(samples[i].path.read_bytes()), gen) for i in test_idx]
        preds = clf.predict_images(imgs)
        pi = np.array([classes.index(p.label) for p in preds])
        accepted = np.array([not p.needs_review for p in preds])
        yt = y[test_idx]
        return {
            "accuracy": mt.accuracy(yt, pi),
            "macro_f1": mt.macro_f1(yt, pi, 6),
            "mean_confidence": float(np.mean([p.confidence for p in preds])),
            "needs_review_rate": float(1 - accepted.mean()),
            "accepted_accuracy": float((pi[accepted] == yt[accepted]).mean())
            if accepted.any()
            else float("nan"),
        }

    robustness = {"clean (same code path)": stress(lambda im, r: im)}
    for name, fn in PERTURBATIONS.items():
        robustness[name] = stress(fn)
        log(
            f"   {name}: acc={robustness[name]['accuracy']:.3f} review={robustness[name]['needs_review_rate']:.2f}"
        )
    report["robustness"] = {
        "note": "synthetic proxies applied to the test images; not field data",
        "results": robustness,
    }

    gen = np.random.default_rng(seed)
    ood_items: list[tuple[str, Image.Image, bool]] = []
    for path in sorted((REPO / "ml" / "artifacts" / "_ood").iterdir()):
        # Trusted local dev files (BMP is not an accepted *upload* format, so bypass the upload
        # validator here instead of widening it).
        with Image.open(path) as opened:
            ood_items.append((f"photo: {path.name}", opened.convert("RGB"), True))
    ood_items += [
        ("synthetic: blank white", Image.new("RGB", (512, 384), (255, 255, 255)), False),
        ("synthetic: blank black", Image.new("RGB", (512, 384), (0, 0, 0)), False),
        ("synthetic: mid grey", Image.new("RGB", (512, 384), (128, 128, 128)), False),
        (
            "synthetic: gaussian noise",
            Image.fromarray(gen.integers(0, 255, (384, 512, 3), dtype=np.uint8)),
            True,
        ),
        (
            "synthetic: colour blocks",
            Image.fromarray(
                np.kron(gen.integers(0, 255, (6, 8, 3)), np.ones((64, 64, 1))).astype(np.uint8)
            ),
            True,
        ),
    ]
    ood = []
    for name, image, _ in ood_items:
        p = clf.predict_images([image])[0]
        ood.append(
            {
                "input": name,
                "predicted": p.label,
                "confidence": p.confidence,
                "novelty_similarity": p.novelty_similarity,
                "needs_review": p.needs_review,
                "reasons": p.review_reasons,
            }
        )
    id_flagged = float(np.mean(proba_test.max(1) < rule["min_confidence"]))
    report["ood"] = {
        "note": "tiny, hand-picked set of NON-waste inputs (ImageNet-style photos and synthetic images); a smoke test, not a benchmark",
        "n": len(ood),
        "flagged_for_review": sum(o["needs_review"] for o in ood),
        "items": ood,
        "in_distribution_test_flagged_by_novelty_gate": float(
            (novelty_all[test_idx] < rule["min_novelty_similarity"]).mean()
        ),
        "in_distribution_test_flagged_by_confidence_gate": id_flagged,
    }

    bytes_list = [samples[i].path.read_bytes() for i in test_idx[:120]]
    clf.predict_bytes(bytes_list[0])
    times = np.array([clf.timed_predict_bytes(b)[1] for b in bytes_list])
    report["latency"] = {
        "n": len(times),
        "p50_ms": float(np.percentile(times, 50)),
        "p95_ms": float(np.percentile(times, 95)),
        "max_ms": float(times.max()),
        "mean_ms": float(times.mean()),
        "scope": "bytes -> decode -> all TTA passes -> head -> calibration -> review decision, single request, no batching",
        "hardware": f"{platform.processor() or platform.machine()}, {__import__('os').cpu_count()} CPU cores, no GPU",
        "interpreter_threads": 2,
    }

    # ---- provenance + files --------------------------------------------------------------------
    report["provenance"] = {
        "version": version,
        "git_commit": git_state()[0],
        "code_tree_clean": git_state()[1],
        "trained_at_utc": trained_at,
        "config_sha256": hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        "dataset_files_digest": files_digest(samples),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scikit_learn": sklearn.__version__,
        "artifact_model_json_sha256": sha256_file(out_dir / "model.json"),
        "artifact_files": manifest["files"],
        "backbones": manifest["backbones"],
    }
    report_dir = REPO / "docs" / "ml" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"waste-classification-{version}.json").write_text(
        json.dumps(report, indent=2, default=float)
    )
    registry = REPO / "ml" / "model_registry" / "waste_classification"
    registry.mkdir(parents=True, exist_ok=True)
    (registry / f"{version}.yaml").write_text(
        yaml.safe_dump(
            {
                "name": config["name"],
                "version": version,
                "status": "candidate",
                "task": "material_category",
                "framework": "tflite (frozen backbone) + numpy linear head",
                "trained_at_utc": report["provenance"]["trained_at_utc"],
                "git_commit": report["provenance"]["git_commit"],
                "code_tree_clean": report["provenance"]["code_tree_clean"],
                "config_sha256": report["provenance"]["config_sha256"],
                "dataset_manifest": config["dataset"]["manifest"],
                "dataset_files_digest": report["provenance"]["dataset_files_digest"],
                "backbones": manifest["backbones"],
                "artifact_files": manifest["files"],
                "artifact_model_json_sha256": report["provenance"]["artifact_model_json_sha256"],
                "classes": classes,
                "tta_variants": manifest["tta_variants"],
                "temperature": temperature,
                "review": manifest["review"],
                "headline_metrics": {
                    "split": "test (grouped, evaluated once)",
                    "accuracy": test_eval["accuracy"],
                    "accuracy_ci95": test_eval["accuracy_ci"],
                    "macro_f1": test_eval["macro_f1"],
                    "macro_f1_ci95": test_eval["macro_f1_ci"],
                    "ece": test_eval["ece"],
                    "latency_p95_ms": report["latency"]["p95_ms"],
                },
                "evaluation_report": f"docs/ml/reports/waste-classification-{version}.json",
                "model_card": f"docs/ml/model-cards/waste-classification-{version}.md",
            },
            sort_keys=False,
        )
    )
    log(
        f"done: test acc={test_eval['accuracy']:.4f} macroF1={test_eval['macro_f1']:.4f} ece={test_eval['ece']:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
