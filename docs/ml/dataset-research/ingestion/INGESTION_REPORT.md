# Ingestion and validation report

**Run date:** 2026-10-20. **Host:** 2 CPU cores, ~3.9 GB RAM, ~18 GB free disk. **Code:** `ml/waste_classification/data/fetch.py`
(TrashNet and the backbones) and the commands below (RealWaste). All raw data live under `datasets/external/` which is
git-ignored; nothing in this report was copied into Git except the manifests and these text/JSON reports.

## Rules applied
- Pinned commits (never a branch name); sources limited to the allow-listed git hosts; no downloaded code was executed.
- Raw data are never modified; derived files (embeddings cache, splits) go under `ml/artifacts/` (git-ignored).
- Every image was decoded with the same validated loader used at serving time (`ml/common/preprocessing/images.py`: format
  allow-list, size cap, EXIF-aware); failures are listed, never skipped silently.
- Exact duplicates found by SHA-256 of the file bytes; near-duplicates by average-linkage clustering of EfficientNet-EdgeTPU-S
  embeddings at cosine similarity ≥ 0.70, **per class** (0.70 is above the 99th percentile of random same-class pairs
  on TrashNet; see `ml/configs/waste_classification.yaml`).
- Splits are group-aware: no near-duplicate group crosses train/validation/test (asserted in code).
- Model selection, calibration (temperature) and the review rule use train/validation only; test is read once.

## Results

| Dataset | Pinned version | Files | Decoded OK | Exact duplicate files | Content digest (SHA-256 over sorted `class/name sha256` lines) |
|---|---|---|---|---|---|
| TrashNet resized | `6fa2b878…` | 2,527 | 2,527 | 3 (2,524 distinct) | `73cfe75b6a3e1bf1d19632514006aad5c26944480f9364402003be9e567b5221` |
| RealWaste | `156e8e91…` | 4,752 | 4,752 | 0 | `59fabef99c26bb25afb86b718981e6fc6e04b6bcba6bd39de5834ee668f432ef` |
| RealWaste ∩ TrashNet | — | — | — | 0 exact overlap (checked by file SHA-256) | — |

Class distributions: TrashNet cardboard 403 / glass 501 / metal 410 / paper 594 / plastic 482 / trash 137;
RealWaste Cardboard 461 / Food Organics 411 / Glass 420 / Metal 790 / Miscellaneous Trash 495 / Paper 500 / Plastic 921 / Textile Trash 318 / Vegetation 436 (all match the sources' stated counts).

Image geometry: TrashNet 512×384 JPEG; RealWaste 524×524 JPEG (every file). No other size or format occurred.

### Leakage audit
| | TrashNet | RealWaste |
|---|---|---|
| Near-duplicate groups | 1,477 | 2,043 |
| Images in a multi-image group | 60.98% | 78.7% |
| Largest group | 35 | 72 |
| Split (train / validation / test) | 1,684 / 422 / 421 | 3,168 / 792 / 792 |
| Group straddling a split | none (asserted) | none (asserted) |

A random image-level split of either dataset would put near-copies of a test image in training and overstate accuracy; the
group-aware split is what makes the held-out numbers meaningful. RealWaste is more redundant than TrashNet, so its
held-out CIs are wide (≈ ±5 points) even with 792 test images.

### Cross-dataset evaluation (no leakage by construction)
The released model never saw RealWaste. All 4,752 images were scored; nothing was fitted on them. Result file:
`experiments/cross-dataset-realwaste.json`. Summary in `DATASET_SELECTION_REPORT.md`.

### Time series
Weekly aggregation, completeness rule, interpolation counts and exclusions per series are recorded in
`experiments/time-series-results.json` (chronological 70/30 split, seasonal-naive/naive/moving-average/SES/damped-Holt/Holt-Winters
baselines, seed 42).

## Reproduce
```bash
python -m venv /tmp/venv-ml && /tmp/venv-ml/bin/pip install -r ml/requirements-dev.txt
PYTHONPATH=. python -m ml.waste_classification.data.fetch            # TrashNet + backbones, hashes verified
git init datasets/external/realwaste-src && cd datasets/external/realwaste-src \
  && git remote add origin https://github.com/sam-single/realwaste.git \
  && git fetch --depth 1 origin 156e8e9154eeb163df30fcfd767f55b19633bb06 && git checkout FETCH_HEAD && cd -
PYTHONPATH=. python -m ml.waste_classification.training.train        # rebuilds the released candidate (~21 min on 2 cores)
PYTHONPATH=. python -m ml.waste_classification.research.cross_dataset realwaste \
  --root datasets/external/realwaste-src/RealWaste \
  --reference-hashes <json list of TrashNet file sha256> \
  --out docs/ml/dataset-research/experiments/cross-dataset-realwaste.json
PYTHONPATH=. python -m ml.waste_classification.research.multi_dataset_experiment \
  --out docs/ml/dataset-research/experiments/multi-dataset-realwaste.json
```
Both research scripts refuse to overwrite an existing result file. The experiment was run twice with identical output.
`train.py` rewrites the tracked report and registry entry with new timestamps and latencies; the learned head
(`head.npz`) and every accuracy figure reproduce bit-for-bit (second independent reproduction, 2026-10-20, trained at 16:56 UTC:
head SHA-256 `0972f2c8…2c64`, test accuracy 0.8670, macro-F1 0.8409, ECE 0.0310), see also `reproducibility-1.0.0.md`.
