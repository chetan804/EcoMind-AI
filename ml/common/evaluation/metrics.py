"""Classification metrics used by every image classifier's evaluation (numpy only).

All functions take integer class labels and, where relevant, a probability matrix ``(n, k)``.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

IntArray = NDArray[np.int_]
FloatArray = NDArray[np.float64]
_EPS = 1e-12


def confusion_matrix(y_true: IntArray, y_pred: IntArray, n_classes: int) -> IntArray:
    matrix = np.zeros((n_classes, n_classes), dtype=np.int_)
    np.add.at(matrix, (y_true, y_pred), 1)
    return matrix


@dataclass(frozen=True)
class ClassReport:
    precision: float
    recall: float
    f1: float
    support: int


def per_class_report(matrix: IntArray) -> list[ClassReport]:
    reports: list[ClassReport] = []
    for k in range(matrix.shape[0]):
        tp = float(matrix[k, k])
        predicted, actual = float(matrix[:, k].sum()), float(matrix[k, :].sum())
        precision = tp / predicted if predicted else 0.0
        recall = tp / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        reports.append(ClassReport(precision, recall, f1, int(actual)))
    return reports


def accuracy(y_true: IntArray, y_pred: IntArray) -> float:
    return float(np.mean(y_true == y_pred)) if len(y_true) else 0.0


def macro_f1(y_true: IntArray, y_pred: IntArray, n_classes: int) -> float:
    reports = per_class_report(confusion_matrix(y_true, y_pred, n_classes))
    return float(np.mean([r.f1 for r in reports]))


def top_k_accuracy(y_true: IntArray, proba: FloatArray, k: int) -> float:
    top = np.argsort(-proba, axis=1)[:, :k]
    return float(np.mean((top == y_true[:, None]).any(axis=1)))


def log_loss(y_true: IntArray, proba: FloatArray) -> float:
    picked = np.clip(proba[np.arange(len(y_true)), y_true], _EPS, 1.0)
    return float(-np.mean(np.log(picked)))


def brier_score(y_true: IntArray, proba: FloatArray) -> float:
    onehot = np.zeros_like(proba)
    onehot[np.arange(len(y_true)), y_true] = 1.0
    return float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))


def expected_calibration_error(
    y_true: IntArray, proba: FloatArray, n_bins: int = 10
) -> tuple[float, list[dict[str, float]]]:
    """Top-label ECE with equal-width bins, plus the per-bin table for a reliability diagram."""
    confidence = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y_true).astype(np.float64)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece, table = 0.0, []
    for low, high in itertools.pairwise(edges):
        mask = (confidence > low) & (confidence <= high) if low > 0 else confidence <= high
        if not mask.any():
            continue
        gap = abs(float(correct[mask].mean()) - float(confidence[mask].mean()))
        ece += mask.mean() * gap
        table.append(
            {
                "low": float(low),
                "high": float(high),
                "count": int(mask.sum()),
                "confidence": float(confidence[mask].mean()),
                "accuracy": float(correct[mask].mean()),
            }
        )
    return float(ece), table


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a proportion (robust for small samples and extreme values)."""
    if total == 0:
        return (0.0, 1.0)
    z = {0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}[confidence]
    p = successes / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    half = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denom
    return (float(max(0.0, centre - half)), float(min(1.0, centre + half)))


def grouped_bootstrap(
    metric: Callable[[IntArray], float],
    groups: IntArray,
    *,
    resamples: int,
    confidence: float,
    seed: int,
) -> tuple[float, float]:
    """Percentile interval of ``metric(sample_indices)`` resampling whole *groups*, so images of
    one object are never treated as independent evidence."""
    rng = np.random.default_rng(seed)
    unique = np.unique(groups)
    members = {g: np.flatnonzero(groups == g) for g in unique}
    values: list[float] = []
    for _ in range(resamples):
        chosen = rng.choice(unique, size=len(unique), replace=True)
        values.append(metric(np.concatenate([members[g] for g in chosen])))
    alpha = (1 - confidence) / 2
    low, high = np.quantile(values, [alpha, 1 - alpha])
    return float(low), float(high)


def selective_curve(
    y_true: IntArray, proba: FloatArray, thresholds: Sequence[float]
) -> list[dict[str, float]]:
    """Coverage (share auto-accepted) and accuracy of the accepted subset per threshold."""
    confidence = proba.max(axis=1)
    correct = proba.argmax(axis=1) == y_true
    rows = []
    for threshold in thresholds:
        accepted = confidence >= threshold
        rows.append(
            {
                "threshold": float(threshold),
                "coverage": float(accepted.mean()),
                "accuracy": float(correct[accepted].mean()) if accepted.any() else float("nan"),
            }
        )
    return rows


def softmax(logits: FloatArray, temperature: float = 1.0) -> FloatArray:
    scaled = logits / temperature
    scaled = scaled - scaled.max(axis=1, keepdims=True)
    exp = np.exp(scaled)
    return np.asarray(exp / exp.sum(axis=1, keepdims=True), dtype=np.float64)


def fit_temperature(y_true: IntArray, logits: FloatArray) -> float:
    """Temperature that minimises validation NLL.

    One scalar cannot memorise labels, so this recalibrates confidence without changing which
    class is predicted. Golden-section search on log T over [e^-3, e^3]; NLL is unimodal in log T.
    """

    def nll(log_t: float) -> float:
        return log_loss(y_true, softmax(logits, float(np.exp(log_t))))

    ratio = (np.sqrt(5.0) - 1.0) / 2.0
    low, high = -3.0, 3.0
    a, b = high - ratio * (high - low), low + ratio * (high - low)
    fa, fb = nll(a), nll(b)
    for _ in range(80):
        if fa < fb:
            high, b, fb = b, a, fa
            a = high - ratio * (high - low)
            fa = nll(a)
        else:
            low, a, fa = a, b, fb
            b = low + ratio * (high - low)
            fb = nll(b)
    return float(np.exp((low + high) / 2.0))
