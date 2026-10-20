"""Pure modelling steps (no I/O): features -> CV selection -> fit -> calibrate -> evaluate.

Kept separate from ``train.py`` (orchestration, files, figures) so each step is unit-testable.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold

from ml.common.evaluation import metrics as mt
from ml.waste_classification.inference.classifier import INPUT_SCALE

Arr = NDArray[np.float64]
F32 = NDArray[np.float32]
Ints = NDArray[np.int_]
N_CLASSES = 6


def fit_head(features: F32, y: Ints, c_value: float) -> LogisticRegression:
    """Multinomial logistic regression on ``(n, n_variants, dim)`` features; every variant of an
    image is a training example with the image's label."""
    n, v, d = features.shape
    model = LogisticRegression(C=c_value, class_weight="balanced", max_iter=2000)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # lbfgs convergence chatter at large C; scores are checked
        model.fit(features.reshape(n * v, d) * INPUT_SCALE, np.repeat(y, v))
    return model


def head_scores(model: LogisticRegression, features: F32) -> Arr:
    """Per-variant linear scores ``(n, n_variants, n_classes)``."""
    n, v, d = features.shape
    scores = model.decision_function(features.reshape(n * v, d) * INPUT_SCALE)
    return np.asarray(scores, dtype=np.float64).reshape(n, v, -1)


def tta_logits(scores: Arr, variant_idx: list[int]) -> Arr:
    return np.asarray(scores[:, variant_idx].mean(axis=1))


@dataclass
class CVResult:
    f1: list[float]
    acc: list[float]
    nll: list[float]
    train_f1: list[float]
    fold_scores: list[Arr]  # held-out per-variant scores per fold
    fold_idx: list[Ints]

    def mean(self, key: str) -> float:
        return float(np.mean(getattr(self, key)))

    def sem(self, key: str) -> float:
        values = getattr(self, key)
        return float(np.std(values, ddof=1) / np.sqrt(len(values)))


def grouped_folds(
    y: Ints, groups: Ints, idx: Ints, n_folds: int, seed: int
) -> list[tuple[Ints, Ints]]:
    splitter = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    return [(idx[a], idx[b]) for a, b in splitter.split(np.zeros(len(idx)), y[idx], groups[idx])]


def cross_validate(
    x: F32, y: Ints, folds: list[tuple[Ints, Ints]], c_value: float, *, augment: bool = True
) -> CVResult:
    """Grouped CV on training images only. Held-out scores are kept for TTA analysis."""
    result = CVResult([], [], [], [], [], [])
    for fit_idx, held_idx in folds:
        train_x = x[fit_idx] if augment else x[fit_idx][:, :1]
        model = fit_head(train_x, y[fit_idx], c_value)
        scores = head_scores(model, x[held_idx])
        pred = scores[:, 0].argmax(axis=1)
        result.f1.append(mt.macro_f1(y[held_idx], pred, N_CLASSES))
        result.acc.append(mt.accuracy(y[held_idx], pred))
        result.nll.append(mt.log_loss(y[held_idx], mt.softmax(scores[:, 0])))
        own = head_scores(model, x[fit_idx][:, :1])[:, 0].argmax(axis=1)
        result.train_f1.append(mt.macro_f1(y[fit_idx], own, N_CLASSES))
        result.fold_scores.append(scores)
        result.fold_idx.append(held_idx)
    return result


def one_se_choice(c_grid: list[float], results: dict[float, CVResult]) -> float:
    """Most regularised C whose mean CV macro-F1 is within one standard error of the best."""
    best_c = max(c_grid, key=lambda c: results[c].mean("f1"))
    threshold = results[best_c].mean("f1") - results[best_c].sem("f1")
    return min(c for c in c_grid if results[c].mean("f1") >= threshold)


def tta_cv_f1(result: CVResult, y: Ints, variant_idx: list[int]) -> tuple[float, float]:
    scores = [
        mt.macro_f1(y[idx], tta_logits(s, variant_idx).argmax(axis=1), N_CLASSES)
        for s, idx in zip(result.fold_scores, result.fold_idx, strict=True)
    ]
    return float(np.mean(scores)), float(np.std(scores, ddof=1) / np.sqrt(len(scores)))


def choose_review_thresholds(
    y: Ints,
    proba: Arr,
    novelty: Arr,
    *,
    target_precision: float,
    novelty_quantile: float,
) -> dict[str, Any]:
    """Pick the review rule on VALIDATION data.

    novelty: flag the ``novelty_quantile`` least familiar images. confidence: the lowest
    threshold at which the auto-accepted predictions reach ``target_precision`` (and at least
    30 images are accepted, so the choice is not driven by a handful of samples).
    """
    min_novelty = float(np.quantile(novelty, novelty_quantile))
    confidence, correct = proba.max(axis=1), proba.argmax(axis=1) == y
    familiar = novelty >= min_novelty
    chosen: float | None = None
    for threshold in np.round(np.arange(0.30, 1.0, 0.01), 2):
        accepted = familiar & (confidence >= threshold)
        if accepted.sum() >= 30 and correct[accepted].mean() >= target_precision:
            chosen = float(threshold)
            break
    met = chosen is not None
    return {
        "min_confidence": chosen if met else 0.99,
        "min_novelty_similarity": min_novelty,
        "target_precision": target_precision,
        "target_met_on_validation": met,
    }


def review_outcome(y: Ints, proba: Arr, novelty: Arr, rule: dict[str, Any]) -> dict[str, float]:
    accepted = (proba.max(axis=1) >= rule["min_confidence"]) & (
        novelty >= rule["min_novelty_similarity"]
    )
    correct = proba.argmax(axis=1) == y
    wrong = ~correct
    n_acc = int(accepted.sum())
    low, high = mt.wilson_interval(int(correct[accepted].sum()), n_acc)
    return {
        "auto_accept_rate": float(accepted.mean()),
        "needs_review_rate": float(1 - accepted.mean()),
        "accepted_accuracy": float(correct[accepted].mean()) if n_acc else float("nan"),
        "accepted_accuracy_ci_low": low,
        "accepted_accuracy_ci_high": high,
        "errors_sent_to_review": float((~accepted & wrong).sum() / max(wrong.sum(), 1)),
        "n_accepted": n_acc,
    }


def evaluate_probabilities(
    y: Ints, proba: Arr, groups: Ints | None, config: dict[str, Any], seed: int
) -> dict[str, Any]:
    pred = proba.argmax(axis=1)
    matrix = mt.confusion_matrix(y, pred, N_CLASSES)
    ece, bins = mt.expected_calibration_error(y, proba)
    out: dict[str, Any] = {
        "n": len(y),
        "accuracy": mt.accuracy(y, pred),
        "macro_f1": mt.macro_f1(y, pred, N_CLASSES),
        "top2_accuracy": mt.top_k_accuracy(y, proba, 2),
        "log_loss": mt.log_loss(y, proba),
        "brier": mt.brier_score(y, proba),
        "ece": ece,
        "mean_confidence": float(proba.max(axis=1).mean()),
        "reliability_bins": bins,
        "confusion_matrix": matrix.tolist(),
        "per_class": [r.__dict__ for r in mt.per_class_report(matrix)],
    }
    if groups is not None:
        boot = config["bootstrap"]
        for key, fn in (
            ("accuracy", lambda i: mt.accuracy(y[i], pred[i])),
            ("macro_f1", lambda i: mt.macro_f1(y[i], pred[i], N_CLASSES)),
        ):
            low, high = mt.grouped_bootstrap(
                fn, groups, resamples=boot["resamples"], confidence=boot["confidence"], seed=seed
            )
            out[f"{key}_ci"] = [low, high]
    return out
