from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pytest

from ml.waste_classification.training import pipeline as pl


def _toy(
    n_per_class: int = 30, dim: int = 16, noise: float = 0.35
) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.int_], npt.NDArray[np.int_]]:
    rng = np.random.default_rng(0)
    centres = rng.normal(size=(6, dim))
    y = np.repeat(np.arange(6), n_per_class)
    x = centres[y][:, None, :] + rng.normal(scale=noise, size=(len(y), 4, dim))
    x /= np.linalg.norm(x, axis=-1, keepdims=True)
    return x.astype(np.float32), y, np.arange(len(y))


def test_fit_head_learns_separable_classes_and_scores_have_expected_shape() -> None:
    x, y, _ = _toy()
    model = pl.fit_head(x, y, 1.0)
    scores = pl.head_scores(model, x)
    assert scores.shape == (len(y), 4, 6)
    assert (pl.tta_logits(scores, [0, 1]).argmax(1) == y).mean() > 0.95


def test_stronger_regularisation_shrinks_the_weights() -> None:
    x, y, _ = _toy()
    weak, strong = pl.fit_head(x, y, 10.0), pl.fit_head(x, y, 0.001)
    assert np.linalg.norm(strong.coef_) < np.linalg.norm(weak.coef_)


def test_grouped_cv_reports_a_train_cv_gap_and_never_leaks_groups() -> None:
    x, y, idx = _toy()
    groups = idx // 3
    folds = pl.grouped_folds(y, groups, idx, 3, 1)
    for fit_i, held_i in folds:
        assert not set(groups[fit_i]) & set(groups[held_i])
    result = pl.cross_validate(x, y, folds, 1.0)
    assert len(result.f1) == 3 and result.mean("f1") > 0.8
    assert result.mean("train_f1") >= result.mean("f1") - 1e-9


def test_one_se_choice_prefers_the_most_regularised_within_one_standard_error() -> None:
    def fake(f1s: list[float]) -> pl.CVResult:
        return pl.CVResult(f1s, f1s, f1s, f1s, [], [])

    results = {
        0.01: fake([0.70, 0.72, 0.71]),
        0.1: fake([0.84, 0.86, 0.85]),
        1.0: fake([0.82, 0.88, 0.85]),
        10.0: fake([0.80, 0.82, 0.81]),
    }
    # best mean is tied between 0.1 and 1.0 (0.85); 0.01 is far outside one SE, 0.1 is chosen
    assert pl.one_se_choice([0.01, 0.1, 1.0, 10.0], results) == 0.1


def test_review_rule_hits_the_target_precision_on_validation() -> None:
    rng = np.random.default_rng(1)
    n = 600
    confidence = rng.uniform(0.4, 1.0, n)
    y = np.zeros(n, dtype=int)
    wrong = rng.random(n) > confidence  # lower confidence -> more errors
    proba = np.zeros((n, 2))
    proba[:, 0] = np.where(wrong, 1 - confidence, confidence)
    proba[:, 1] = 1 - proba[:, 0]
    novelty = rng.uniform(0.6, 1.0, n)
    rule = pl.choose_review_thresholds(
        y, proba, novelty, target_precision=0.95, novelty_quantile=0.02
    )
    assert rule["target_met_on_validation"]
    outcome = pl.review_outcome(y, proba, novelty, rule)
    assert outcome["accepted_accuracy"] >= 0.95
    assert 0 < outcome["auto_accept_rate"] < 1
    assert outcome["errors_sent_to_review"] > 0.3
    assert rule["min_novelty_similarity"] == pytest.approx(np.quantile(novelty, 0.02))


def test_review_rule_reports_when_the_target_cannot_be_met() -> None:
    proba = np.tile([0.6, 0.4], (100, 1))
    y = np.r_[np.zeros(50, dtype=int), np.ones(50, dtype=int)]  # 50% accurate at any confidence
    rule = pl.choose_review_thresholds(
        y, proba, np.ones(100), target_precision=0.95, novelty_quantile=0.0
    )
    assert rule["target_met_on_validation"] is False
    assert rule["min_confidence"] == 0.99  # fail safe: send (nearly) everything to review


def test_evaluate_probabilities_contains_the_protocol_metrics() -> None:
    x, y, idx = _toy()
    model = pl.fit_head(x, y, 1.0)
    proba = np.exp(pl.tta_logits(pl.head_scores(model, x), [0]))
    proba /= proba.sum(1, keepdims=True)
    cfg = {"bootstrap": {"resamples": 50, "confidence": 0.95}}
    out = pl.evaluate_probabilities(y, proba, idx // 3, cfg, 1)
    for key in (
        "accuracy",
        "macro_f1",
        "ece",
        "log_loss",
        "brier",
        "confusion_matrix",
        "per_class",
        "accuracy_ci",
        "macro_f1_ci",
    ):
        assert key in out
    low, high = out["accuracy_ci"]
    assert low <= out["accuracy"] <= high
    assert sum(sum(r) for r in out["confusion_matrix"]) == len(y)
