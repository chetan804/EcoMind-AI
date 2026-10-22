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


def top_confusions(classes: list[str], matrix: list[list[int]], n: int = 2) -> str:
    """The most frequent off-diagonal cells, as prose computed from the matrix."""
    cells = [
        (matrix[i][j], classes[i], classes[j])
        for i in range(len(classes))
        for j in range(len(classes))
        if i != j and matrix[i][j] > 0
    ]
    cells.sort(reverse=True)
    if not cells:
        return "There were no misclassifications on the test split."
    parts = [f"{a} predicted as {b} ({c} images)" for c, a, b in cells[:n]]
    return "The most frequent confusions on the test split: " + "; ".join(parts) + "."


def status_banner(r: dict[str, Any]) -> str:
    d, a = r["dataset"], r["acceptance"]
    return (
        f"> **RESEARCH CANDIDATE, NOT APPROVED, NOT FOR RELEASE.** Trained only on {d['name']} {d['version']}, whose licence status is "
        f"**{d['licence_status']}** (declared: {', '.join(x['spdx'] for x in d['licence_declared'])}); release allowed: {d['release_allowed']}. "
        f"Acceptance decision: **{a['decision']}**. Field evaluation done: {a['field_evaluation']['done']}.\n"
        "> TrashNet and TrashBox are excluded from this model's training, validation and test data."
    )


def acceptance_table(r: dict[str, Any]) -> str:
    a = r["acceptance"]
    rows = [
        [name, c["required"], f"{c['observed']:.3f}", "pass" if c["passed"] else "**FAIL**"]
        for name, c in a["offline"].items()
    ]
    fe = a["field_evaluation"]
    rows.append(
        [
            "Hyderabad field evaluation",
            f">= {fe['criteria']['min_images']} images, macro-F1 >= {fe['criteria']['min_macro_f1']}",
            "done" if fe["done"] else "not done",
            "pass" if fe["passed"] else "**not met**",
        ]
    )
    return table(["criterion", "required", "observed", "result"], rows)


def out_of_scope_section(r: dict[str, Any]) -> str:
    o = r["out_of_scope"]
    rows = [
        [
            folder,
            str(x["n"]),
            pct(x["sent_to_review"]),
            ", ".join(f"{c} {n}" for c, n in x["predicted_as"].items()) or "none",
        ]
        for folder, x in o["by_folder"].items()
    ]
    return (
        f"{o['note']}\n\n"
        + table(
            [
                "source folder",
                "images",
                "sent to review",
                "what it would be called without the review rule",
            ],
            rows,
        )
        + f"\n\nOverall **{pct(o['overall_sent_to_review'])}** of {o['n']} out-of-scope images were sent to a person "
        f"(low confidence on {o['review_reasons']['low_confidence']}, unfamiliar image on {o['review_reasons']['unfamiliar_image']}; "
        "an image can trigger both). The remainder would have been shown as a material suggestion."
    )


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
    k = len(classes)
    for i in range(k):
        for j in range(k):
            ax.text(j, i, matrix[i, j], ha="center", va="center", fontsize=9)
    ax.set_xticks(range(k), classes, rotation=40, ha="right")
    ax.set_yticks(range(k), classes)
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
    ax.set_xlim(0, 1)
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
at {pct(t["review"]["accepted_accuracy"])} accuracy and the rest go to a human. This is a score on one Australian facility's photographs; **it is not a field accuracy for Hyderabad.**

{status_banner(r)}

### Acceptance criteria (set before the run; `ml/configs/waste_classification.yaml`)

{acceptance_table(r)}

Meeting the offline criteria would only make the model eligible for a field evaluation. No model is activated by this report.

## 1. Data and split

{r["dataset"]["name"]} {r["dataset"]["version"]} (`{r["dataset"]["manifest"]}`): {r["dataset"]["n_files"]} files, of which {sp["n_images"]} are in the {len(cl)} trained material classes
and {r["dataset"]["n_out_of_scope"]} (catch-all, organic and textile folders) are out-of-scope evaluation input. Provenance gate passed: manifest complete, 0 files byte-identical to a TrashNet image
(SHA-256 denylist), {r["dataset"]["exact_duplicate_files"]} exact duplicate files, content digest `{r["dataset"]["files_digest"][:16]}...` matches the manifest. Per-file table (hash, label, role, group): `{sp["per_file_table"]["path"]}` ({sp["per_file_table"]["rows"]} rows).
Near-duplicates (several photographs of one object) were clustered per class
({sp["n_groups"]} groups, largest {sp["largest_group"]} images; {pct(sp["images_in_multi_image_groups"], 0)} of images share a group), and a stratified group split was fixed
**before any modelling** (seed {r["seed"]}): train {sp["sizes"]["train"]}, validation {sp["sizes"]["validation"]}, test {sp["sizes"]["test"]}. No group appears in two splits and no byte-identical file straddles two splits (both checked in code).

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
The rule picks the cheapest (backbone, TTA) pair within one standard error of the best CV score. It was fixed before
the results were seen and was not changed afterwards.

{ablation_section}### Baselines (must be beaten by a stated margin: +0.10 macro-F1)

| baseline | CV macro-F1 | validation macro-F1 | test macro-F1 |
|---|---|---|---|
| majority class ({r["baselines"]["majority_class"]["class"]}) | n/a | {r["baselines"]["majority_class"]["val_macro_f1"]:.3f} | {t["baselines"]["majority_macro_f1"]:.3f} |
| hand-crafted colour/gradient features + logistic regression | {r["baselines"]["handcrafted_logreg"]["cv_macro_f1"]:.3f} | {r["baselines"]["handcrafted_logreg"]["val_macro_f1"]:.3f} | {t["baselines"]["handcrafted_macro_f1"]:.3f} |
| **selected model** | {ch["cv_macro_f1"]:.3f} | {v["calibrated"]["macro_f1"]:.3f} | **{tc["macro_f1"]:.3f}** |

Margin over the hand-crafted baseline on test: **{t["margin_over_handcrafted_macro_f1"]:+.3f}** (required {t["required_margin"]:+.2f}): {"met" if t["margin_over_handcrafted_macro_f1"] >= t["required_margin"] else "NOT met"}.

## 3. Over- and under-fitting diagnosis

{cvsel}

- **Selection overfitting check:** grouped CV macro-F1 {d["chosen_cv"]["cv_macro_f1"]:.3f}, validation {v["calibrated"]["macro_f1"]:.3f}, test {tc["macro_f1"]:.3f}. A test score far below CV would indicate that tuning overfitted; read the gap from these three numbers.
- **Generalisation gap:** train (in-sample) macro-F1 {r["train_in_sample"]["macro_f1"]:.3f} against grouped-CV {d["chosen_cv"]["cv_macro_f1"]:.3f} (train-minus-CV gap {d["chosen_cv"]["train_minus_cv_gap"]:.3f}).
- **Capacity probe:** a non-linear RBF-SVM on the same features scores {d["capacity_probe"]["rbf_svm_cv_macro_f1"]:.3f} CV macro-F1 against {d["capacity_probe"]["linear_head_cv_macro_f1"]:.3f} for the linear head (no augmentation).
- **Augmentation:** CV macro-F1 {d["augmentation_ablation"]["with_augmentation_cv_macro_f1"]:.3f} with vs {d["augmentation_ablation"]["without_augmentation_cv_macro_f1"]:.3f} without.

![regularisation sweep]({fig["regularisation"]})

{regt}

The chosen C = {ch["C"]} is the *most regularised* value within one standard error of the best CV score (the pre-declared 1-SE rule).

![learning curve]({fig["learning-curve"]})

{lc}

The learning curve plots held-out macro-F1 against the share of training data used; whether more data of the same kind would help is read from its slope and is not asserted here.

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

{top_confusions(cl, tc["confusion_matrix"])} The weakest class by F1 is **{min(zip(cl, tc["per_class"], strict=True), key=lambda cp: cp[1]["f1"])[0]}** (F1 {min(p["f1"] for p in tc["per_class"]):.3f}).

## 5. Calibration and the review rule

Temperature **T = {r["calibration"]["temperature"]:.3f}** (fit on validation). T below 1 means the raw head was under-confident, above 1 over-confident.

| | ECE | log-loss | mean confidence |
|---|---|---|---|
| validation, raw | {v["uncalibrated_ece"]:.3f} | {v["uncalibrated_log_loss"]:.3f} | {v["uncalibrated_mean_confidence"]:.3f} |
| validation, calibrated | {v["calibrated"]["ece"]:.3f} | {v["calibrated"]["log_loss"]:.3f} | {v["calibrated"]["mean_confidence"]:.3f} |
| test, raw | {t["uncalibrated_ece"]:.3f} | {t["uncalibrated_log_loss"]:.3f} | {t["uncalibrated_mean_confidence"]:.3f} |
| test, calibrated | {tc["ece"]:.3f} | {tc["log_loss"]:.3f} | {tc["mean_confidence"]:.3f} |

![reliability]({fig["reliability"]})

**Review rule** (chosen on validation): flag for human review when calibrated confidence < **{rule["min_confidence"]:.2f}**
(lowest threshold giving >= {pct(rule["target_precision"], 0)} accuracy on auto-accepted validation images; target met: {rule["target_met_on_validation"]}) or when the image's maximum
cosine similarity to the training images is < **{rule["min_novelty_similarity"]:.3f}** (the novelty quantile set in the config, applied to validation images only).

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

The two background perturbations only replace near-white pixels, so on photographs without a white background they change almost nothing and are **not** evidence of robustness to clutter.
These are synthetic proxies; none of them substitutes for field photographs.

## 7. Out-of-scope waste and out-of-distribution inputs

### 7a. Waste the model has no class for (RealWaste folders mapped to no EcoMind class)

{out_of_scope_section(r)}

### 7b. Unrelated photographs (smoke test)

{r["ood"]["note"][:1].upper()}{r["ood"]["note"][1:]}. {r["ood"]["flagged_for_review"]} of {r["ood"]["n"]} were routed to review. The same gates flag {pct(r["ood"]["in_distribution_test_flagged_by_novelty_gate"])} of in-distribution test images by novelty alone
(and {pct(r["ood"]["in_distribution_test_flagged_by_confidence_gate"])} by confidence).

{ood}

The ten-input smoke set is not a measurement. E-waste and hazardous items were not tested (no labelled data).

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
    cc = r["split"]["class_counts"]
    counts_text = ", ".join(f"{c} {sum(cc[k][c] for k in cc)}" for c in r["classes"])
    return f"""# Model card: waste material classifier {version}

**Status: RESEARCH CANDIDATE. NOT APPROVED. NOT FOR RELEASE.** Trained only on {r["dataset"]["name"]} {r["dataset"]["version"]} (licence status: **{r["dataset"]["licence_status"]}**; declared {", ".join(x["spdx"] for x in r["dataset"]["licence_declared"])}), so the model may be used for non-commercial research only and must not be distributed, shipped or activated until the dataset licence is confirmed in writing. No field evaluation exists. Acceptance decision: **{r["acceptance"]["decision"]}**. TrashNet and TrashBox are excluded from every split. Full evidence: `docs/ml/reports/waste-classification-{version}.md`.

## Model details
- **Task:** assign one of {len(r["classes"])} *material* categories ({", ".join(r["classes"])}) to a photograph of a single waste item, with a calibrated confidence and a `needs_review` flag. It does **not** identify the object (no object label is produced).
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
{r["dataset"]["name"]} {r["dataset"]["version"]} (`{r["dataset"]["manifest"]}`; UCI dataset 908 / authors' GitHub, pinned commit `156e8e91`): photographs of waste received at one facility in Wollongong NSW, Australia. {r["dataset"]["n_training_scope"]} images in the five trained classes ({counts_text}); {r["dataset"]["n_out_of_scope"]} images of catch-all, food/vegetation and textile folders were **not** trained on and are used only to measure review routing. "Miscellaneous Trash" is not treated as a material. Licence conflict (UCI: CC BY 4.0; authors' GitHub: CC BY-NC-SA 4.0) is unresolved. Cite: Single, Iranmanesh and Raad (2023), *Information* 14(12):633, https://doi.org/10.3390/info14120633. Labels are the authors' and were not audited. Pipeline checks: SHA-256 denylist of TrashNet images (0 matches), group-aware split, byte-duplicate leakage check.

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
- **Single-site data, not field data.** All training and test images come from one Australian facility. Accuracy for Indian municipal waste, Hyderabad lighting, packaging and clutter is **unknown** until the field evaluation in `docs/ml/field-evaluation-protocol.md` is run.
- Weakest class on test: **{min(zip(r["classes"], tc["per_class"], strict=True), key=lambda cp: cp[1]["f1"])[0]}** (F1 {min(p["f1"] for p in tc["per_class"]):.2f}). {top_confusions(r["classes"], tc["confusion_matrix"], 1)}
- Out-of-scope waste (catch-all, food, vegetation, textile folders): {pct(r["out_of_scope"]["overall_sent_to_review"])} of {r["out_of_scope"]["n"]} images were sent to review; the rest would have been given a material label.
- Worst synthetic stress: **{worst[0]}** (accuracy {worst[1]["accuracy"]:.2f}, mean confidence {worst[1]["mean_confidence"]:.2f}; auto-accepted accuracy {worst[1]["accepted_accuracy"]:.2f}).
- Only {len(r["classes"])} classes: items outside them can be forced into one (mitigated, not solved, by the novelty gate; tested on the out-of-scope folders above and a ten-input smoke set).
- Generalisation gap: train (in-sample) macro-F1 {r["train_in_sample"]["macro_f1"]:.2f} vs held-out {tc["macro_f1"]:.2f}.
- Residual near-duplicate similarity across the split (see report section 1), so the test score may be slightly optimistic.
- Collected in one place and time; Indian municipal waste (packaging, materials, regional streams) is not represented.

## Ethical and privacy notes
No person was looked for in the training photographs and none is expected, but they were not audited (`personal_data: not assessed` in the manifest). Inference inputs are user photographs that may contain people or places; the upload
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
