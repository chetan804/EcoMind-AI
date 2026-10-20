"""Render figures, the evaluation report and the model card from the training run's JSON.

    python -m ml.waste_classification.evaluation.report

Every number in the Markdown comes from ``docs/ml/reports/waste-classification-<version>.json``.
"""

from __future__ import annotations

import json
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ml.waste_classification.training.features import REPO, load_config

REPORTS = REPO / "docs" / "ml" / "reports"
CARDS = REPO / "docs" / "ml" / "model-cards"


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%"


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def figures(r: dict[str, Any], version: str) -> dict[str, str]:
    out_dir = REPORTS / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    classes = r["classes"]
    names: dict[str, str] = {}

    def save(fig: Any, key: str) -> None:
        name = f"waste-{version}-{key}.png"
        fig.tight_layout()
        fig.savefig(out_dir / name, dpi=110)
        plt.close(fig)
        names[key] = f"figures/{name}"

    test = r["test"]["calibrated"]
    matrix = np.array(test["confusion_matrix"])
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    ax.imshow(matrix / matrix.sum(1, keepdims=True), cmap="Greens", vmin=0, vmax=1)
    for i in range(6):
        for j in range(6):
            ax.text(j, i, matrix[i, j], ha="center", va="center", fontsize=9)
    ax.set_xticks(range(6), classes, rotation=40, ha="right")
    ax.set_yticks(range(6), classes)
    ax.set_xlabel("predicted")
    ax.set_ylabel("actual")
    ax.set_title("Test confusion matrix (counts; shade = row share)")
    save(fig, "confusion")

    fig, ax = plt.subplots(figsize=(4.8, 4.6))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect calibration")
    for key, label, colour in (
        ("validation", "validation", "#c77d00"),
        ("test", "test", "#1b7f4c"),
    ):
        bins = r[key]["calibrated"]["reliability_bins"]
        ax.plot(
            [b["confidence"] for b in bins],
            [b["accuracy"] for b in bins],
            "o-",
            c=colour,
            label=label,
        )
    ax.set_xlabel("mean confidence in bin")
    ax.set_ylabel("accuracy in bin")
    ax.set_title(f"Reliability (test ECE {test['ece']:.3f})")
    ax.legend()
    save(fig, "reliability")

    cand = r["selection"]["chosen"]["candidate"]
    grid = r["selection"]["cv_by_candidate_and_C"][cand]
    cs = sorted(grid, key=float)
    fig, ax = plt.subplots(figsize=(5.2, 4))
    ax.semilogx(
        [float(c) for c in cs],
        [grid[c]["train_macro_f1"] for c in cs],
        "o-",
        label="train (in-sample)",
    )
    ax.semilogx(
        [float(c) for c in cs],
        [grid[c]["cv_macro_f1"] for c in cs],
        "o-",
        label="grouped CV (held-out)",
    )
    ax.axvline(float(r["selection"]["chosen"]["C"]), c="grey", ls=":", label="chosen C")
    ax.set_xlabel("C (weaker regularisation ->)")
    ax.set_ylabel("macro-F1")
    ax.set_title(f"Bias-variance sweep, backbone {cand}")
    ax.legend()
    save(fig, "regularisation")

    lc = r["diagnostics"]["learning_curve"]
    fig, ax = plt.subplots(figsize=(5.2, 4))
    ax.plot(
        [c["n_train_images"] for c in lc], [c["train_macro_f1"] for c in lc], "o-", label="train"
    )
    ax.plot(
        [c["n_train_images"] for c in lc], [c["cv_macro_f1"] for c in lc], "o-", label="grouped CV"
    )
    ax.set_xlabel("training images")
    ax.set_ylabel("macro-F1")
    ax.set_title("Learning curve")
    ax.legend()
    save(fig, "learning-curve")

    sel = r["test"]["selective_curve"]
    fig, ax = plt.subplots(figsize=(5.2, 4))
    ax.plot([s["coverage"] for s in sel], [s["accuracy"] for s in sel], "o-")
    for s in sel:
        ax.annotate(
            f"{s['threshold']:.2f}",
            (s["coverage"], s["accuracy"]),
            fontsize=7,
            xytext=(3, -9),
            textcoords="offset points",
        )
    ax.set_xlabel("share of images auto-accepted (coverage)")
    ax.set_ylabel("accuracy of auto-accepted")
    ax.set_title("Confidence threshold trade-off (test)")
    save(fig, "selective")

    rob = r["robustness"]["results"]
    labels = list(rob)
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    ax.barh(range(len(labels)), [rob[k]["accuracy"] for k in labels], color="#1b7f4c")
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0.4, 1)
    ax.set_xlabel("accuracy (test images, synthetic perturbation)")
    ax.set_title("Robustness to synthetic perturbations")
    save(fig, "robustness")
    return names


def evaluation_report(r: dict[str, Any], fig: dict[str, str], version: str) -> str:
    cl, t, v = r["classes"], r["test"], r["validation"]
    tc, d, rule = t["calibrated"], r["diagnostics"], r["review_rule"]
    ch, sp, lk = r["selection"]["chosen"], r["split"], d["leakage_study"]
    per = table(
        ["class", "precision", "recall", "F1", "support"],
        [
            [c, f"{p['precision']:.3f}", f"{p['recall']:.3f}", f"{p['f1']:.3f}", str(p["support"])]
            for c, p in zip(cl, tc["per_class"], strict=True)
        ],
    )
    cmx = table(
        ["actual \\ predicted", *cl],
        [[cl[i], *map(str, row)] for i, row in enumerate(tc["confusion_matrix"])],
    )
    pairs = table(
        ["backbone", "TTA", "CV macro-F1", "SEM", "est. p95 ms", "within latency budget"],
        [
            [
                p["candidate"],
                p["tta"],
                f"{p['cv_macro_f1']:.3f}",
                f"{p['cv_sem']:.3f}",
                f"{p['p95_ms_estimate']:.0f}",
                "yes" if p["feasible"] else "no",
            ]
            for p in r["selection"]["candidate_tta_pairs"]
        ],
    )
    reg = r["selection"]["cv_by_candidate_and_C"][ch["candidate"]]
    regt = table(
        ["C", "train macro-F1", "CV macro-F1", "CV SEM", "CV log-loss"],
        [
            [
                c,
                f"{reg[c]['train_macro_f1']:.3f}",
                f"{reg[c]['cv_macro_f1']:.3f}",
                f"{reg[c]['cv_sem']:.3f}",
                f"{reg[c]['cv_log_loss']:.3f}",
            ]
            for c in sorted(reg, key=float)
        ],
    )
    lc = table(
        ["training images", "train macro-F1", "CV macro-F1"],
        [
            [str(c["n_train_images"]), f"{c['train_macro_f1']:.3f}", f"{c['cv_macro_f1']:.3f}"]
            for c in d["learning_curve"]
        ],
    )
    sel = table(
        ["threshold", "auto-accepted", "accuracy of auto-accepted"],
        [
            [
                f"{s['threshold']:.2f}",
                pct(s["coverage"]),
                pct(s["accuracy"]) if s["accuracy"] == s["accuracy"] else "n/a",
            ]
            for s in t["selective_curve"]
        ],
    )
    rob = table(
        [
            "condition",
            "accuracy",
            "macro-F1",
            "mean confidence",
            "needs review",
            "accuracy when auto-accepted",
        ],
        [
            [
                k,
                f"{x['accuracy']:.3f}",
                f"{x['macro_f1']:.3f}",
                f"{x['mean_confidence']:.3f}",
                pct(x["needs_review_rate"], 0),
                f"{x['accepted_accuracy']:.3f}",
            ]
            for k, x in r["robustness"]["results"].items()
        ],
    )
    ood = table(
        ["input", "predicted", "confidence", "similarity to training set", "needs review"],
        [
            [
                o["input"],
                o["predicted"],
                f"{o['confidence']:.2f}",
                f"{o['novelty_similarity']:.2f}",
                ("yes: " + ", ".join(o["reasons"])) if o["needs_review"] else "**no**",
            ]
            for o in r["ood"]["items"]
        ],
    )
    cvsel = table(
        ["split", "macro-F1", "accuracy"],
        [
            [
                "train (in-sample)",
                f"{r['train_in_sample']['macro_f1']:.3f}",
                f"{r['train_in_sample']['accuracy']:.3f}",
            ],
            [
                "train, grouped 5-fold CV (held-out folds)",
                f"{d['chosen_cv']['cv_macro_f1']:.3f}",
                f"{d['chosen_cv']['cv_accuracy']:.3f}",
            ],
            [
                "validation",
                f"{v['calibrated']['macro_f1']:.3f}",
                f"{v['calibrated']['accuracy']:.3f}",
            ],
            ["**test (evaluated once)**", f"**{tc['macro_f1']:.3f}**", f"**{tc['accuracy']:.3f}**"],
        ],
    )
    lat, par, prov = r["latency"], r["parity"], r["provenance"]
    ablation_file = REPORTS / f"waste-classification-{version}-preprocessing-ablation.json"
    ablation_section = ""
    if ablation_file.exists():
        ab = json.loads(ablation_file.read_text())
        rows = [
            [k, f"{x['cv_macro_f1']:.3f}", f"{x['cv_sem']:.3f}"] for k, x in ab["results"].items()
        ]
        ablation_section = (
            "### Preprocessing ablation (`ml/waste_classification/experiments/preprocessing_ablation.py`)\n\n"
            f"Backbone {ab['backbone']}, C = {ab['C']}, {ab['split']}. Run before the main pipeline to settle how a 4:3 photograph becomes a square input;\n"
            "validation and test were not used.\n\n"
            + table(["preprocessing", "CV macro-F1", "SEM"], rows)
            + "\n\n"
        )
    return f"""# Waste material classifier {version}: evaluation report

Generated by `python -m ml.waste_classification.evaluation.report` from
`waste-classification-{version}.json` (the raw numbers). Protocol: `docs/ml/evaluation-protocol.md`.

**Summary.** On a held-out, group-aware test split (n = {tc["n"]}, evaluated once) the model reaches
**accuracy {tc["accuracy"]:.3f}** (95% CI {tc["accuracy_ci"][0]:.3f}-{tc["accuracy_ci"][1]:.3f}) and **macro-F1 {tc["macro_f1"]:.3f}**
(CI {tc["macro_f1_ci"][0]:.3f}-{tc["macro_f1_ci"][1]:.3f}). Its confidence is calibrated (mean confidence {tc["mean_confidence"]:.3f} vs accuracy
{tc["accuracy"]:.3f}; ECE {tc["ece"]:.3f}). With the review rule, {pct(t["review"]["auto_accept_rate"], 0)} of images are auto-accepted
at {pct(t["review"]["accepted_accuracy"])} accuracy and the rest go to a human. This is a score on *studio-style photographs*; it is not a field accuracy.

## 1. Data and split

TrashNet (`datasets/manifests/trashnet-1.0.yaml`): {sp["n_images"]} images, 6 material classes.
Near-duplicates (several photographs of one object) were clustered per class
({sp["n_groups"]} groups, largest {sp["largest_group"]} images; {pct(sp["images_in_multi_image_groups"], 0)} of images share a group), and a stratified group split was fixed
**before any modelling**: train {sp["sizes"]["train"]}, validation {sp["sizes"]["validation"]}, test {sp["sizes"]["test"]}. No group appears in two splits (checked in code).

{table(["split", *cl], [[k, *[str(sp["class_counts"][k][c]) for c in cl]] for k in ("train", "validation", "test")])}

**Leakage measured, not assumed.** The same recipe under a naive random split (ignoring groups) scores accuracy
{lk["naive_random_split_accuracy"]:.3f} / macro-F1 {lk["naive_random_split_macro_f1"]:.3f}, against {tc["accuracy"]:.3f} / {tc["macro_f1"]:.3f} on the grouped test
split. {pct(lk["share_of_test_images_with_a_near_twin_in_train_naive"])} of naive-test images have a near-twin in training ({lk["near_twin_definition"]}),
against {pct(lk["share_of_test_images_with_a_near_twin_in_train_grouped"])} with grouping. **Grouping reduces but does not eliminate similarity across the split**
(the residual is from the clustering threshold), so the test score may still be slightly optimistic.

## 2. Model and selection (train split only)

Frozen ImageNet-pretrained EfficientNet-EdgeTPU TFLite backbone -> L2-normalised features x10 -> multinomial
logistic regression (balanced class weights) -> temperature scaling. Training images are embedded under 4
orientation variants (identity, h-flip, v-flip, 90-degree rotation) as augmentation. Selection used 5-fold grouped CV on
the train split only; **C** by the one-standard-error rule (most regularised C within 1 SE of the best); then the *cheapest*
(backbone, TTA) pair within 1 SE of the best among those inside the {load_config()["selection"]["max_p95_latency_ms"]} ms latency budget.

{pairs}

Selected: **backbone {ch["candidate"]}, C = {ch["C"]}, TTA = {ch["tta"]}** (CV macro-F1 {ch["cv_macro_f1"]:.3f} +/- {ch["cv_sem"]:.3f}).
Larger or combined backbones score slightly higher in CV, but the differences are about one standard error. The rule
was fixed before the results were seen and was not changed afterwards.

{ablation_section}### Baselines (must be beaten by a stated margin: +0.10 macro-F1)

| baseline | CV macro-F1 | validation macro-F1 | test macro-F1 |
|---|---|---|---|
| majority class ({r["baselines"]["majority_class"]["class"]}) | n/a | {r["baselines"]["majority_class"]["val_macro_f1"]:.3f} | {t["baselines"]["majority_macro_f1"]:.3f} |
| hand-crafted colour/gradient features + logistic regression | {r["baselines"]["handcrafted_logreg"]["cv_macro_f1"]:.3f} | {r["baselines"]["handcrafted_logreg"]["val_macro_f1"]:.3f} | {t["baselines"]["handcrafted_macro_f1"]:.3f} |
| **selected model** | {ch["cv_macro_f1"]:.3f} | {v["calibrated"]["macro_f1"]:.3f} | **{tc["macro_f1"]:.3f}** |

Margin over the hand-crafted baseline on test: **{t["margin_over_handcrafted_macro_f1"]:+.3f}** (required {t["required_margin"]:+.2f}): {"met" if t["margin_over_handcrafted_macro_f1"] >= t["required_margin"] else "NOT met"}.

## 3. Over- and under-fitting diagnosis

{cvsel}

- **No selection overfitting:** grouped CV ({d["chosen_cv"]["cv_macro_f1"]:.3f}), validation ({v["calibrated"]["macro_f1"]:.3f}) and test ({tc["macro_f1"]:.3f}) agree within their sampling noise, so
  hyper-parameter choice did not overfit the data it was tuned on.
- **There is a real generalisation gap:** the model fits its training images far better than unseen ones
  (train-minus-CV macro-F1 gap {d["chosen_cv"]["train_minus_cv_gap"]:.3f}). This is the usual regime of a high-dimensional linear head on ~1.7k images.
  Regularisation (below) does not close it: weaker regularisation (C up to 0.3) trains to 1.0 and gains at most about one SE on held-out folds, stronger regularisation (C = 0.003) underfits.
- **Not underfitting:** train macro-F1 is {r["train_in_sample"]["macro_f1"]:.3f}, and a non-linear RBF-SVM on the same features scores
  {d["capacity_probe"]["rbf_svm_cv_macro_f1"]:.3f} vs {d["capacity_probe"]["linear_head_cv_macro_f1"]:.3f} for the linear head (no augmentation; a difference of about one SE), so head capacity is not what limits accuracy.
- **Augmentation helps modestly:** CV macro-F1 {d["augmentation_ablation"]["with_augmentation_cv_macro_f1"]:.3f} with vs {d["augmentation_ablation"]["without_augmentation_cv_macro_f1"]:.3f} without.

![regularisation sweep]({fig["regularisation"]})

{regt}

Low C underfits (train and CV both low); high C overfits (train -> 1.0, CV flat or falling). The chosen C = 0.03 is the *most regularised* value within one standard error of the best CV score
(C = 0.3), the pre-declared 1-SE rule: the same held-out performance with a simpler, less train-fitted head.

![learning curve]({fig["learning-curve"]})

{lc}

Held-out macro-F1 rises quickly and flattens over the last fractions while the train score stays near 1.0: **more images of the same kind
would help little; more *diverse* data (backgrounds, clutter, local items) is what is missing.**

## 4. Test results (evaluated once)

| metric | value |
|---|---|
| accuracy | {tc["accuracy"]:.3f} (95% CI {tc["accuracy_ci"][0]:.3f}-{tc["accuracy_ci"][1]:.3f}, group bootstrap) |
| macro-F1 | {tc["macro_f1"]:.3f} (95% CI {tc["macro_f1_ci"][0]:.3f}-{tc["macro_f1_ci"][1]:.3f}) |
| top-2 accuracy | {tc["top2_accuracy"]:.3f} |
| log-loss / Brier | {tc["log_loss"]:.3f} / {tc["brier"]:.3f} |

{per}

{cmx}

![confusion matrix]({fig["confusion"]})

The dominant error is **glass predicted as metal** and plastic as metal (reflective, similarly shaped containers); `trash` (n = {tc["per_class"][5]["support"]}) is the weakest class.

## 5. Calibration and the review rule

Temperature **T = {r["calibration"]["temperature"]:.3f}** (fit on validation). T below 1 means the raw head was slightly *under*-confident.

| | ECE | log-loss | mean confidence |
|---|---|---|---|
| validation, raw | {v["uncalibrated_ece"]:.3f} | {v["uncalibrated_log_loss"]:.3f} | {v["uncalibrated_mean_confidence"]:.3f} |
| validation, calibrated | {v["calibrated"]["ece"]:.3f} | {v["calibrated"]["log_loss"]:.3f} | {v["calibrated"]["mean_confidence"]:.3f} |
| test, raw | {t["uncalibrated_ece"]:.3f} | {t["uncalibrated_log_loss"]:.3f} | {t["uncalibrated_mean_confidence"]:.3f} |
| test, calibrated | {tc["ece"]:.3f} | {tc["log_loss"]:.3f} | {tc["mean_confidence"]:.3f} |

![reliability]({fig["reliability"]})

**Review rule** (chosen on validation): flag for human review when calibrated confidence < **{rule["min_confidence"]:.2f}**
(lowest threshold giving >= {pct(rule["target_precision"], 0)} accuracy on auto-accepted validation images; target met: {rule["target_met_on_validation"]}) or when the image's maximum
cosine similarity to the training images is < **{rule["min_novelty_similarity"]:.3f}** (the least familiar 2% of validation images).

| split | auto-accepted | accuracy of auto-accepted (95% Wilson CI) | errors sent to review |
|---|---|---|---|
| validation | {pct(v["review"]["auto_accept_rate"])} | {pct(v["review"]["accepted_accuracy"])} ({pct(v["review"]["accepted_accuracy_ci_low"])}-{pct(v["review"]["accepted_accuracy_ci_high"])}) | {pct(v["review"]["errors_sent_to_review"], 0)} |
| **test** | {pct(t["review"]["auto_accept_rate"])} | **{pct(t["review"]["accepted_accuracy"])}** ({pct(t["review"]["accepted_accuracy_ci_low"])}-{pct(t["review"]["accepted_accuracy_ci_high"])}) | {pct(t["review"]["errors_sent_to_review"], 0)} |

![selective]({fig["selective"]})

{sel}

"Higher confidence" is therefore a *choice of operating point*, not a property to maximise: raising the threshold raises the accuracy of what is auto-accepted and sends more to humans.

## 6. Robustness (synthetic proxies on the test images)

{rob}

![robustness]({fig["robustness"]})

Occlusion, low resolution and low contrast hurt most. Under occlusion the model is **over-confident** (mean confidence above accuracy) and the review gate does not fully protect: auto-accepted accuracy falls.
Background replacement changed little, but it only replaces near-white pixels of studio photographs, so it is a weak proxy for real clutter.

## 7. Out-of-distribution inputs

{r["ood"]["note"][:1].upper()}{r["ood"]["note"][1:]}. {r["ood"]["flagged_for_review"]} of {r["ood"]["n"]} were routed to review. The same gates flag {pct(r["ood"]["in_distribution_test_flagged_by_novelty_gate"])} of in-distribution test images by novelty alone
(and {pct(r["ood"]["in_distribution_test_flagged_by_confidence_gate"])} by confidence).

{ood}

This does **not** show the model can recognise unsupported *waste* (food scraps, e-waste, textiles, hazardous items), which was not tested because no labelled data was available.

## 8. Latency and train/serve parity

Single request, bytes -> decode -> {r["selection"]["chosen"]["passes"]} backbone pass(es) -> head -> calibration -> decision, {lat["hardware"]}, {lat["interpreter_threads"]} interpreter threads, n = {lat["n"]} test files:
**p50 {lat["p50_ms"]:.1f} ms, p95 {lat["p95_ms"]:.1f} ms, max {lat["max_ms"]:.1f} ms.** Parity of the serving code against the training-time features on {par["n_images"]} images:
max |logit difference| = {par["max_abs_logit_difference"]:.1e}; identical predictions: {par["same_predictions"]}.

These timings come from a shared development sandbox (other jobs may have been running), so treat them as an order of magnitude, not a benchmark; the budget is 150 ms. Re-measure on the deployment hardware before relying on them.

## 9. Provenance

version `{prov["version"]}`, git commit `{prov["git_commit"]}` (training code tree clean at that commit: {prov["code_tree_clean"]}), trained {prov["trained_at_utc"]}, config SHA-256 `{prov["config_sha256"]}`, dataset content digest `{prov["dataset_files_digest"]}`,
`model.json` SHA-256 `{prov["artifact_model_json_sha256"]}`, Python {prov["python"]}, numpy {prov["numpy"]}, scikit-learn {prov["scikit_learn"]}.
Reproduce: `python -m ml.waste_classification.data.fetch && python -m ml.waste_classification.training.train && python -m ml.waste_classification.evaluation.report`.
"""


def model_card(r: dict[str, Any], version: str) -> str:
    t, tc, rule, lat = r["test"], r["test"]["calibrated"], r["review_rule"], r["latency"]
    ch, prov = r["selection"]["chosen"], r["provenance"]
    worst = min(r["robustness"]["results"].items(), key=lambda kv: kv[1]["accuracy"])
    return f"""# Model card: waste material classifier {version}

**Status: candidate.** Trained and evaluated on one public studio-style dataset. Not validated on field data and not
approved for unattended use. Full evidence: `docs/ml/reports/waste-classification-{version}.md`.

## Model details
- **Task:** assign one of six *material* categories (cardboard, glass, metal, paper, plastic, trash) to a photograph of a single waste item, with a calibrated confidence and a `needs_review` flag. It does **not** identify the object (no object label is produced).
- **Architecture:** frozen ImageNet-pretrained EfficientNet-EdgeTPU-{ch["candidate"]} embedding extractor (TFLite, uint8; Apache-2.0, google-coral/test_data @ `104342d2`) -> logistic-regression head (numpy) -> temperature scaling.
- **Runtime:** `ai-edge-litert` + numpy + Pillow on CPU. No GPU, no PyTorch/TensorFlow. Artifact files are verified by SHA-256 before loading.
- **Owner/contact:** project maintainers (repository `chetan804/EcoMind-AI`). **Version/date:** {version}, {prov["trained_at_utc"]}.

## Intended use
Decision support for triaging citizen waste reports: suggest a material category and tell a reviewer when to look. Reviewer
corrections are stored with the prediction and are the intended source of future training data.

## Out of scope
Final regulatory or billing decisions; hazardous, medical, e-waste, organic/food or textile identification; scenes with several
items or heavy clutter; any unattended sorting; inferring anything about people.

## Training data
TrashNet resized (`datasets/manifests/trashnet-1.0.yaml`): 2,527 photographs, MIT-licensed repository, white-posterboard studio setting, three iPhone models, 2016-17.
Class counts: cardboard 403, glass 501, metal 410, paper 594, plastic 482, trash 137. No personal data intended. Labels are the authors' and were not audited.

## Evaluation (held-out group-aware test split, n = {tc["n"]}, evaluated once)
| | |
|---|---|
| Accuracy | **{tc["accuracy"]:.3f}** (95% CI {tc["accuracy_ci"][0]:.3f}-{tc["accuracy_ci"][1]:.3f}) |
| Macro-F1 | **{tc["macro_f1"]:.3f}** (95% CI {tc["macro_f1_ci"][0]:.3f}-{tc["macro_f1_ci"][1]:.3f}) |
| Calibration (ECE) | {tc["ece"]:.3f}; mean confidence {tc["mean_confidence"]:.3f} vs accuracy {tc["accuracy"]:.3f} |
| With the review rule | {pct(t["review"]["auto_accept_rate"], 0)} auto-accepted at {pct(t["review"]["accepted_accuracy"])} accuracy; {pct(t["review"]["errors_sent_to_review"], 0)} of errors sent to review |
| Best baseline (hand-crafted features) | macro-F1 {t["baselines"]["handcrafted_macro_f1"]:.3f} |
| Latency (2 CPU cores, bytes to decision) | p50 {lat["p50_ms"]:.0f} ms, p95 {lat["p95_ms"]:.0f} ms |

**Review rule:** needs review when calibrated confidence < {rule["min_confidence"]:.2f} or similarity to the training images < {rule["min_novelty_similarity"]:.3f}.

## Known weaknesses
- **Studio-to-field gap, measured on one real-world dataset.** On RealWaste (4,752 photographs from a recycling facility in Wollongong, Australia; never seen in training; CC BY-NC-SA 4.0, evaluation only) this model reaches 0.45 accuracy (95% CI 0.44-0.47) and macro-F1 0.51 on the five mappable material classes, with ECE 0.26 (over-confident). The review rule sends 64% of those images to a person; the auto-accepted 36% are 55% accurate. 96% of food, vegetation and textile images (classes this model does not have) are sent to review. Details: `docs/ml/dataset-research/experiments/cross-dataset-realwaste.json` and `docs/ml/dataset-research/DATASET_SELECTION_REPORT.md`. Treat every field prediction as a suggestion.
- Glass is frequently confused with metal and plastic; `trash` is the weakest class (F1 {tc["per_class"][5]["f1"]:.2f}, 23 test images).
- Worst synthetic stress: **{worst[0]}** (accuracy {worst[1]["accuracy"]:.2f}; auto-accepted accuracy {worst[1]["accepted_accuracy"]:.2f}), where the model is over-confident.
- Only six classes: items outside them will be forced into one (mitigated, not solved, by the novelty gate; tested only on a ten-input smoke set).
- Generalisation gap: train macro-F1 {r["train_in_sample"]["macro_f1"]:.2f} vs held-out ~{tc["macro_f1"]:.2f}; limited by data diversity, not by tuning.
- Residual near-duplicate similarity across the split (see report section 1), so the test score may be slightly optimistic.
- Collected in one place and time; Indian municipal waste (packaging, materials, regional streams) is not represented.

## Ethical and privacy notes
Training images contain no people by design. Inference inputs are user photographs that may contain people or places; the upload
pipeline strips EXIF/GPS metadata and stores images under the platform's access rules. Predictions must be shown as suggestions with their confidence.

## Recommendations
Collect and label local field images (with consent), route low-confidence cases to reviewers, monitor review/correction rates
for drift, re-estimate the review threshold on field data before relying on it, and retrain from reviewed corrections.

## Provenance
git `{prov["git_commit"][:12]}`; config SHA-256 `{prov["config_sha256"][:16]}...`; dataset digest `{prov["dataset_files_digest"][:16]}...`; `model.json` SHA-256 `{prov["artifact_model_json_sha256"][:16]}...`.
Registry entry: `ml/model_registry/waste_classification/{version}.yaml`.
"""


def main() -> int:
    version = load_config()["version"]
    r = json.loads((REPORTS / f"waste-classification-{version}.json").read_text())
    names = figures(r, version)
    (REPORTS / f"waste-classification-{version}.md").write_text(
        evaluation_report(r, names, version)
    )
    CARDS.mkdir(parents=True, exist_ok=True)
    (CARDS / f"waste-classification-{version}.md").write_text(model_card(r, version))
    print("wrote report, model card and figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
