# Dataset selection report

**Date:** 2026-10-20. Companion files: [`DATASET_CATALOG.md`](DATASET_CATALOG.md), [`dataset_manifest.yaml`](dataset_manifest.yaml),
[`REJECTED_DATASETS.md`](REJECTED_DATASETS.md), [`ingestion/INGESTION_REPORT.md`](ingestion/INGESTION_REPORT.md).
Raw results: `experiments/cross-dataset-realwaste.json`, `experiments/multi-dataset-realwaste.json`, `experiments/trashbox-experiment.json` (added 2026-10-21, §4b).

## 1. Decision summary

| Question | Decision | Evidence |
|---|---|---|
| Which waste-image model is the released candidate? | **`waste-classification 1.0.0` (TrashNet only, MIT) stays the single candidate, not activated by default** | reproduced bit-for-bit (§2) |
| Is it good enough for field use? | **No.** On real facility photos it reaches 0.45 accuracy | §3 |
| Does more real-world data help? | **Yes, a lot** (+28 points on real photos) — but the only reachable labelled real-world set (RealWaste) is non-commercial | §4 |
| Is a RealWaste-trained model released? | **No.** Experiment only; no artifact written; never auto-activated | licence in the manifest |
| New taxonomy classes (organic, textile, e-waste, medical, battery)? | **None added.** No legitimately licensed, reachable labelled data. They stay `unsupported`→ review | §5 |
| Does TrashBox (e-waste, medical) help? | **It adds two classes the product lacks and fits its own photos well, but it does not close the real-world gap.** Research only, under verbal permission the owner reports; not released | §4b |
| What closes the gap legitimately? | Local, consented field photos labelled through the app's own **review queue** (`/classify/review`) plus a licensed external set (TACO images whose licences are verified at source, see `TACO_LICENCE_AUDIT.md`; TrashBox only with a written permission and licence from its authors) | §6 |

The product therefore behaves honestly today: predictions carry a calibrated confidence, 64% of real-world images go to a
person, and the model card states the measured field result.

## 2. Baseline reproduction (TrashNet)

`python -m ml.waste_classification.training.train` was re-run from scratch on 2026-10-20 from the pinned sources.
Result: `head.npz` and `novelty_reference.npy` are **bit-identical** to the published artifact; held-out test accuracy 0.867
(95% CI 0.813–0.912), macro-F1 0.841 (0.781–0.887), ECE 0.031 — unchanged. Only timestamps and latencies differ
(`reproducibility-1.0.0.md`). The group-aware split puts 421 images (23 `trash`) in test; the weakest class is `trash`
(F1 0.653).

## 3. Cross-dataset generalisation of the released model (RealWaste, never seen)

Everything below is computed by `ml/waste_classification/research/cross_dataset.py` over **all** 4,752 images; nothing was
tuned on them. Plain bootstrap CIs over images (RealWaste has no object identifiers; near-duplicates make the intervals a
little too narrow).

| View | n | Accuracy (95% CI) | Macro-F1 | ECE | Auto-accepted | Accuracy of auto-accepted |
|---|---|---|---|---|---|---|
| 5 clean classes (cardboard, glass, metal, paper, plastic) | 3,092 | **0.454** (0.437–0.472) | 0.514 | 0.263 | 36.4% | 55.3% |
| + Miscellaneous Trash → `trash` (approximate mapping) | 3,587 | 0.463 (0.447–0.479) | 0.457 | 0.243 | 33.1% | 55.9% |

Per class (5 clean classes) recall: cardboard 0.24, glass 0.43, metal 0.55, paper 0.46, plastic 0.49; precision 0.48–0.80.
The dominant failure is **under-recall plus drift to `trash`** when the approximate class is included: 233 of 461 cardboard,
247 of 500 paper, 222 of 921 plastic and 217 of 790 metal images are called `trash` (confusion matrices in the JSON). Mean confidence is 0.71 against 0.45
accuracy: the model is **over-confident off-distribution**, which is exactly what temperature scaling on in-distribution data
cannot fix.

Classes the model does not have (food organics, vegetation, textile; 1,165 images): the review rule sent **95.5%** to a person
(food 97.6%, vegetation 99.8%, textile 87.1%). Without the gate they would have been called trash, cardboard, metal, paper….
Across all 4,752 images the gate triggered `low_confidence` 3,332 times and `unfamiliar_image` 1,614 times.

**Reading.** The 0.867 TrashNet score is a studio score. The review rule is useful (it removes most OOD inputs and lifts
accepted accuracy), but 55% accuracy on accepted real photos is not acceptable for unattended use. Every field prediction is a
suggestion.

## 4. Multi-dataset experiment (experiment only; RealWaste licence prevents release)

Protocol (fixed before looking at test numbers, `multi_dataset_experiment.py`): frozen backbone embeddings (identity view,
no TTA); logistic-regression head; **C chosen on validation macro-F1** from {0.01, 0.03, 0.1, 0.3}; **temperature and review rule
fitted on validation**; group-aware splits for both datasets (TrashNet: the released model's own split; RealWaste: same
procedure, 3,168/792/792); test read once; 1,000 group-bootstrap resamples. Experiment taxonomy has 8 classes (organic =
Food Organics + Vegetation; textile). "Shared 6" = the six classes every training mixture can predict.

### 4.1 Accuracy on the shared six classes
| Backbone | Training data | Class weights | C | TrashNet test: acc (95% CI) | macro-F1 | RealWaste test, 6 shared classes: acc (95% CI) | macro-F1 | auto-accepted / accuracy of accepted (RealWaste) |
|---|---|---|---|---|---|---|---|---|
| S | TrashNet | balanced | 0.3 | 0.874 (0.83-0.91) | 0.838 | 0.503 (0.42-0.58) | 0.459 | 38% / 71.9% |
| S | RealWaste | balanced | 0.1 | 0.629 (0.55-0.69) | 0.562 | 0.788 (0.74-0.84) | 0.787 | 57% / 94.7% |
| S | TrashNet + RealWaste | balanced | 0.1 | 0.831 (0.78-0.87) | 0.771 | 0.769 (0.72-0.82) | 0.764 | 54% / 93.8% |
| M | TrashNet | balanced | 0.3 | 0.874 (0.82-0.92) | 0.857 | 0.508 (0.44-0.57) | 0.483 | 39% / 64.3% |
| M | TrashNet | unbalanced | 0.3 | 0.874 (0.82-0.92) | 0.844 | 0.505 (0.44-0.57) | 0.471 | 52% / 65.6% |
| M | RealWaste | balanced | 0.3 | 0.594 (0.51-0.66) | 0.525 | 0.788 (0.74-0.83) | 0.791 | 65% / 92.2% |
| M | RealWaste | unbalanced | 0.3 | 0.603 (0.53-0.67) | 0.531 | 0.794 (0.75-0.84) | 0.793 | 62% / 93.6% |
| M | TrashNet + RealWaste | balanced | 0.3 | 0.817 (0.76-0.87) | 0.768 | 0.773 (0.72-0.82) | 0.768 | 55% / 94.2% |
| M | TrashNet + RealWaste | unbalanced | 0.1 | 0.817 (0.76-0.87) | 0.752 | 0.784 (0.73-0.83) | 0.773 | 57% / 93.8% |
| L | TrashNet | balanced | 0.3 | 0.893 (0.85-0.93) | 0.873 | 0.560 (0.48-0.64) | 0.513 | 43% / 78.5% |
| L | RealWaste | balanced | 0.1 | 0.696 (0.62-0.76) | 0.618 | 0.796 (0.74-0.84) | 0.789 | 63% / 91.8% |
| L | TrashNet + RealWaste | balanced | 0.3 | 0.841 (0.79-0.88) | 0.804 | 0.793 (0.74-0.84) | 0.785 | 63% / 91.5% |

| Backbone | Training data | RealWaste test, all 8 classes: acc (95% CI) | macro-F1 (95% CI) | ECE | organic F1 | textile F1 | trash F1 |

### 4.2 Eight-class models on all of RealWaste test (n = 792)
| S | RealWaste | 0.812 (0.77-0.85) | 0.796 (0.74-0.84) | 0.023 | 0.95 | 0.77 | 0.62 |
| S | TrashNet + RealWaste | 0.799 (0.75-0.84) | 0.779 (0.73-0.82) | 0.031 | 0.95 | 0.76 | 0.60 |
| M | RealWaste | 0.809 (0.77-0.85) | 0.793 (0.74-0.83) | 0.025 | 0.93 | 0.75 | 0.63 |
| M (unbalanced) | RealWaste | 0.822 (0.78-0.86) | 0.802 (0.75-0.84) | 0.031 | 0.96 | 0.78 | 0.64 |
| M | TrashNet + RealWaste | 0.803 (0.76-0.84) | 0.783 (0.73-0.82) | 0.036 | 0.94 | 0.78 | 0.57 |
| M (unbalanced) | TrashNet + RealWaste | 0.809 (0.76-0.85) | 0.785 (0.74-0.82) | 0.031 | 0.94 | 0.78 | 0.59 |
| L | RealWaste | 0.821 (0.78-0.86) | 0.803 (0.75-0.84) | 0.029 | 0.95 | 0.82 | 0.62 |
| L | TrashNet + RealWaste | 0.819 (0.77-0.86) | 0.800 (0.75-0.84) | 0.026 | 0.96 | 0.80 | 0.61 |

| Model trained on | Organic+textile test images wrongly auto-accepted (model has no such class) |
| TrashNet, backbone S, balanced | 2.6% of 194 |
| TrashNet, backbone M, balanced | 3.6% of 194 |
| TrashNet, backbone M, unbalanced | 4.1% of 194 |

### 4.3 What the TrashNet-only models do with classes they do not have

### 4.4 Findings
1. **Domain shift dominates.** TrashNet-only heads score 0.87–0.89 on TrashNet and 0.50–0.56 on real facility photos,
   for every backbone. The gap (33–37 points) is far larger than any difference between backbones, balancing or regularisation.
2. **Real photos fix most of it.** Training on RealWaste lifts real-photo accuracy to 0.79–0.80 (6 classes) and 0.81–0.82
   (8 classes); calibration is good on the matching domain (ECE 0.02–0.04) and auto-accepted accuracy reaches ≈ 92–95% at
   54–65% coverage.
3. **Mixing costs studio accuracy.** The mixture loses 4–6 points on TrashNet (M: 0.874 → 0.817; L: 0.893 → 0.841) while
   matching RealWaste-only accuracy on real photos (0.77–0.79). The mixture is the better deployment candidate if a studio-like
   input matters; real-photo-only if it does not.
4. **Bigger backbone helps modestly.** L is 2–5 points better than M/S on most views, with overlapping CIs. Its single-pass p95 latency estimate is
   36.1 ms against 12.9 ms for M in the published 1.0.0 selection log (38.9 and 23.0 ms in the rebuild run, which shared the CPU);
   both are inside the 150 ms CPU budget.
5. **Class weighting made no detectable difference** (balanced vs none: all CIs overlap); `trash` stays the weakest class (F1 0.57–0.64).
6. **Textile and organic become learnable** (organic F1 0.93–0.96, textile 0.75–0.82) *when* labelled data exist.
7. **Statistical caveat.** The RealWaste test slice has 598 shared-class images in 792; CIs are ±4–5 points, so differences below ≈ 5 points
   (S vs M vs L, balanced vs not) are not established. These are single-split results on one dataset from one facility.
8. **Not tested:** fine-tuning the backbone (CPU-only sandbox, no PyTorch), data augmentation on RealWaste (the augmentation
   ablation for 1.0.0 is in its report), other real-world datasets (unreachable), and field data from India.

## 4b. TrashBox experiment (research only; no model written, registered or activated)

**Status of the data.** TrashBox has no licence. The owner reported on 2026-10-21 that its authors gave verbal permission; nothing
is in writing, so for this project it is research input only. Manifest: `datasets/manifests/trashbox-research-1.0.yaml`. The
script (`ml/waste_classification/research/trashbox_experiment.py`) writes no model, refuses to overwrite its result file and was
run once; the design (below) was fixed before any number was seen.

**Data handling.** Only `TrashBox_train_set` (14,282 images; the sub-folder tree is a duplicate). A seeded sample of at most 1,000
images per class (7,000). Dropped before splitting and reported in the JSON: 14 undecodable files, 68 exact duplicates inside
TrashBox, **385 exact copies of TrashNet images** and 5 near-copies of TrashNet images (S-embedding cosine ≥ 0.85); 6,528 images in
4,829 near-duplicate groups remain. Across the whole tree 819 files are byte-identical to TrashNet images, so TrashBox itself
republishes material its authors did not create; whatever the authors say about their own rights, it cannot cover those images or
the unrecorded sources of the rest. RealWaste (shared five classes, 3,092 images, 0 dropped) served only as an external test set.

**Method.** Same frozen EfficientNet-EdgeTPU-M features, logistic regression, temperature and review rule as the released
pipeline, in an 8-class taxonomy (TrashNet's six plus `e_waste`, `medical`). Three training mixtures (TrashNet only; TrashBox only;
both), each class-balanced. C, temperature and the review rule were chosen on validation data of the mixture only; each test set
was read once. TrashNet used the released model's exact split; TrashBox the same group-aware procedure (6 folds). Intervals are
95% grouped bootstrap.

| Trained on → tested on | TrashNet only | TrashBox only | TrashNet + TrashBox |
|---|---|---|---|
| TrashNet test, 5 shared materials (n = 398), accuracy | **0.882** (0.833–0.927) | 0.661 (0.582–0.730) | 0.862 (0.819–0.900) |
| TrashBox test, 5 shared materials (n = 756), accuracy | 0.541 (0.487–0.590) | **0.845** (0.813–0.875) | 0.837 (0.804–0.866) |
| TrashBox test, all 7 classes (n = 1,088), accuracy | 0.376 (0.336–0.417) | **0.867** (0.844–0.889) | 0.859 (0.836–0.883) |
| TrashBox test, 7 classes, macro-F1 | 0.338 | 0.865 | 0.859 |
| **RealWaste, 5 shared materials (n = 3,092), accuracy** | 0.462 (0.429–0.493) | 0.460 (0.426–0.496) | **0.479** (0.450–0.508) |
| RealWaste, share auto-accepted by the review rule | 41% | 37% | 41% |
| Expected calibration error on TrashNet test / RealWaste | 0.033 / 0.261 | 0.104 / 0.208 | **0.016 / 0.214** |

Per-class F1 on the TrashBox test for the mixture: e-waste 0.919, medical 0.886; the five materials 0.81–0.87. Full per-class
numbers, rules and sizes are in the JSON.

**Findings.**
1. A TrashNet-only model does not transfer to TrashBox: 0.54 on the five shared materials and, naturally, 0 on e-waste and medical.
   The reverse is also poor (TrashBox-only on TrashNet 0.66). The two datasets look different (studio photographs vs web photographs).
2. Training on both keeps TrashNet performance within noise of the TrashNet-only model (0.862 vs 0.882, intervals overlap) while
   reaching 0.84 on TrashBox photos, and it is the best calibrated option (ECE 0.016). So *if* TrashBox could be used, a mixture is the
   sensible way to use it and e-waste and medical become learnable classes (F1 ≈ 0.89–0.92 on TrashBox's own test).
3. **None of this carries over to real facility photos.** On RealWaste accuracy is 0.46–0.48 for all three and the difference
   between mixtures is inside the intervals; TrashBox does not close the gap that RealWaste itself closes (§4). The TrashBox test
   score therefore says the model fits web photographs of waste, not that it works on a collection route or in a facility.
4. Consequences: the e-waste/medical result is interesting for the taxonomy but is **not** a reason to ship anything. The decision
   in §1 stands: 1.0.0 stays the single non-default candidate; adding TrashBox to a released model needs written permission and a
   licence from the authors **and** a plan for the third-party images inside it; the real fix remains in-domain, consented photos.

**Limits.** One split and one seed per dataset; TrashBox's own test is in the same web-photo domain as its training data (grouped by
near-duplicates, but photographers and sources are unknown, so some residual leakage cannot be excluded and 0.84–0.87 is probably
optimistic); 1,000 images per class cap; RealWaste maps only five classes (its "Miscellaneous Trash" is not used here); a
RealWaste image the model labels `e_waste` or `medical` counts as wrong for the TrashBox-trained mixtures; the RealWaste region
(Australia) is not the target region (Hyderabad); CPU-only, frozen backbone, no fine-tuning.

## 5. Why no new classes were added

A class needs adequate, legitimately licensed, labelled images and a held-out test. `organic` and `textile` have them only in
RealWaste (non-commercial); `e_waste`/`medical` only in TrashBox (no licence on file; verbal permission reported, §4b); `battery` nowhere reachable. Adding any of
them would mean shipping a model whose training data we may not use. They stay `unsupported`; the review gate is the mitigation
and its measured effect is §3 (96% of unsupported-class images go to review).

## 6. Recommended path (owner decisions are marked)

1. **Keep 1.0.0 as a non-default candidate** and keep the review gate mandatory. (Done.)
2. **Owner decision A:** is the deployment *non-commercial research/education* and is CC BY-NC-SA ShareAlike acceptable? If yes,
   a `1.1.0-research` model trained on TrashNet + RealWaste (M or L backbone, mixture) is a justified, clearly-labelled
   research candidate; its model card would carry the licence. The experiment above indicates ≈ +28 points on real photos.
   If no, skip.
3. **Owner decision B (partly done):** the owner reports verbal permission from the TrashBox authors (2026-10-21). Still needed before
   any use in a released model: written permission and a licence statement, and an answer on the third-party images in the dataset
   (819 files are byte-identical to TrashNet; the rest have no recorded source). The experiment (§4b) shows the gain is on
   TrashBox-like photos, not on real facility photos. Alternatively supply TACO/Flickr images by an owner-run download with a
   per-image licence audit.
4. **Collect in-domain data legitimately:** every reviewer correction in `/classify/review` is a labelled field example linked
   to a prediction and a person. After enough volume, retrain with a group-aware split by reporting site/date and re-estimate the
   review threshold on that data.
5. Before any activation: field acceptance test on locally collected images, with the pass criteria set in advance.

## 7. Limits of this evidence
Single split per dataset; one real-world dataset from one Australian facility; mapping of Miscellaneous Trash → `trash` is
approximate; CIs for RealWaste in §3 ignore near-duplicate clustering; CPU latency was measured on a shared 2-core sandbox; no
Indian waste images were available; the RealWaste paper could not be retrieved, so its authors and year are not cited here.
