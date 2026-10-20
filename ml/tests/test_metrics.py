from __future__ import annotations

import numpy as np
import pytest

from ml.common.evaluation import metrics as m


def test_confusion_matrix_and_per_class_report() -> None:
    y_true = np.array([0, 0, 1, 1, 2, 2])
    y_pred = np.array([0, 1, 1, 1, 2, 0])
    matrix = m.confusion_matrix(y_true, y_pred, 3)
    assert matrix.tolist() == [[1, 1, 0], [0, 2, 0], [1, 0, 1]]
    reports = m.per_class_report(matrix)
    assert reports[1].precision == pytest.approx(2 / 3) and reports[1].recall == 1.0
    assert reports[0].support == 2
    assert m.accuracy(y_true, y_pred) == pytest.approx(4 / 6)


def test_macro_f1_hand_computed() -> None:
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([0, 1, 1, 1])
    # class0: P=1 R=.5 F1=2/3 ; class1: P=2/3 R=1 F1=.8
    assert m.macro_f1(y_true, y_pred, 2) == pytest.approx((2 / 3 + 0.8) / 2)


def test_class_never_predicted_scores_zero_not_nan() -> None:
    report = m.per_class_report(m.confusion_matrix(np.array([0, 1]), np.array([0, 0]), 2))
    assert report[1].f1 == 0.0 and report[1].precision == 0.0


def test_log_loss_brier_and_top_k() -> None:
    proba = np.array([[0.7, 0.2, 0.1], [0.1, 0.1, 0.8]])
    y = np.array([0, 2])
    assert m.log_loss(y, proba) == pytest.approx(-(np.log(0.7) + np.log(0.8)) / 2)
    assert m.brier_score(y, proba) == pytest.approx(
        ((0.09 + 0.04 + 0.01) + (0.01 + 0.01 + 0.04)) / 2
    )
    assert m.top_k_accuracy(np.array([1, 1]), proba, 2) == pytest.approx(0.5)
    assert m.log_loss(y, np.array([[0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])) < 40  # clipped, finite


def test_ece_is_zero_for_a_perfectly_calibrated_and_large_for_an_overconfident_model() -> None:
    rng = np.random.default_rng(0)
    n = 20000
    confidence = rng.uniform(0.5, 1.0, n)
    correct = rng.random(n) < confidence  # accuracy equals confidence by construction
    proba = np.stack([confidence, 1 - confidence], axis=1)
    y = np.where(correct, 0, 1)
    ece, table = m.expected_calibration_error(y, proba)
    assert ece < 0.02 and sum(row["count"] for row in table) == n
    overconfident = np.tile([0.99, 0.01], (1000, 1))
    wrong_half = np.r_[np.zeros(500, dtype=int), np.ones(500, dtype=int)]
    assert m.expected_calibration_error(wrong_half, overconfident)[0] == pytest.approx(
        0.49, abs=0.01
    )


def test_wilson_interval_properties() -> None:
    low, high = m.wilson_interval(95, 100)
    assert 0.88 < low < 0.95 < high < 0.99
    assert m.wilson_interval(0, 0) == (0.0, 1.0)
    assert m.wilson_interval(10, 10)[1] == 1.0 and m.wilson_interval(10, 10)[0] > 0.7


def test_grouped_bootstrap_is_wider_when_groups_are_large() -> None:
    # Ten homogeneous groups (all 1s or all 0s) of ten images each: heavily clustered evidence.
    y = np.repeat(np.array([1, 0] * 5), 10)
    singleton = np.arange(100)
    clustered = np.repeat(np.arange(10), 10)

    def metric(idx: np.ndarray) -> float:
        return float(y[idx].mean())

    narrow = m.grouped_bootstrap(metric, singleton, resamples=400, confidence=0.95, seed=1)
    wide = m.grouped_bootstrap(metric, clustered, resamples=400, confidence=0.95, seed=1)
    assert (wide[1] - wide[0]) > 1.5 * (narrow[1] - narrow[0])  # 10 groups, not 100 samples
    assert m.grouped_bootstrap(metric, singleton, resamples=50, confidence=0.9, seed=3) == (
        m.grouped_bootstrap(metric, singleton, resamples=50, confidence=0.9, seed=3)
    )  # seeded


def test_selective_curve_trades_coverage_for_accuracy() -> None:
    proba = np.array([[0.95, 0.05], [0.9, 0.1], [0.6, 0.4], [0.55, 0.45]])
    y = np.array([0, 0, 1, 0])
    rows = m.selective_curve(y, proba, [0.5, 0.8, 0.99])
    assert [r["coverage"] for r in rows] == [1.0, 0.5, 0.0]
    assert rows[1]["accuracy"] == 1.0 and rows[0]["accuracy"] == pytest.approx(0.75)
    assert np.isnan(rows[2]["accuracy"])


def test_softmax_and_temperature_scaling_recovers_overconfidence() -> None:
    assert m.softmax(np.array([[1.0, 2.0, 3.0]])).sum() == pytest.approx(1.0)
    assert m.softmax(np.array([[0.0, 5.0]]), 5.0)[0, 1] < m.softmax(np.array([[0.0, 5.0]]))[0, 1]
    rng = np.random.default_rng(0)
    n = 6000
    truth_logits = rng.normal(0, 2.0, (n, 3))
    y = np.array([rng.choice(3, p=p) for p in m.softmax(truth_logits)])
    temperature = m.fit_temperature(y, truth_logits * 3.0)  # model that is 3x too sharp
    assert temperature == pytest.approx(3.0, rel=0.15)
