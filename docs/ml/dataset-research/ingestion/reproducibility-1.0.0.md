# Model 1.0.0 reproduction check

**Date:** 2026-10-20. **Command:** `PYTHONPATH=. python -m ml.waste_classification.training.train`
(clean environment, backbones and TrashNet re-fetched from their pinned sources, same
`ml/configs/waste_classification.yaml`, code at commit `e45026e`).

| Item | Published (commit `12c93a5`) | Re-run | Result |
|---|---|---|---|
| `head.npz` SHA-256 | `0972f2c8…2c64` | identical | **bit-identical** |
| `novelty_reference.npy` SHA-256 | `61e60fe1…5221` | identical | **bit-identical** |
| Test accuracy / macro-F1 / ECE | 0.867 / 0.841 / 0.031 | 0.8670 / 0.8409 / 0.0310 | identical |
| Selected backbone, C, T | M, 0.03, 0.901 | M, 0.03, 0.901 | identical |
| `model.json` SHA-256 | `389d4316…3102` | `0a7871b8…d896` | differs: file embeds `trained_at_utc`, `git_commit`, `code_tree_clean` |
| Latency p50 / p95 (ms) | 23.1 / 29.6 | 26.4 / 30.9 | differs: the re-run shared 2 CPUs with other jobs |
| Per-pass p95 estimates used in backbone selection | — | higher | same cause (contention); selection outcome unchanged |

**Reading:** the learned parameters and every accuracy/calibration number are deterministic and
reproduce exactly. Only provenance and wall-clock figures change, as expected. The tracked
report, card and registry entry were therefore left at the published values (restoring them is
deliberate: the re-run's timing was measured under load and its provenance names an uncommitted
tree).
