# Paper readiness (as of 2026-10-22)

**Verdict: the software and documents are ready for a project report and a supervised demonstration. They are not yet
sufficient for a peer-reviewed research paper.** This file lists what a reviewer would accept, what they would object
to, and the owner-only actions that close each gap. Nothing here is a claim about acceptance by any venue; venue scope,
fees and AI-disclosure rules were not verified and must be read on the venue's own site.

## 1. What is solid enough to report
| Item | Evidence |
|---|---|
| A working, tested, audited platform from report to verified recovery | 787 backend, 386 frontend, 61 ML, 147 contract and 61 browser tests (`results.md` section 6); CI green on `main` |
| Reproducible, provenance-gated classifier pipeline (fails closed on missing licence evidence, prohibited data or leakage) | `ml/waste_classification/data/provenance.py`, `datasets/manifests/realwaste-2.0.yaml`, 118 ML tests; model `2.0.0` trained three times on 2026-10-22 from the same inputs (the last from a clean code tree) with identical test metrics (0.8953 / 0.8960 / 0.0364) and identical `head.npz` and `novelty_reference.npy` SHA-256 hashes (same machine; not yet reproduced on another) |
| Honest evaluation on a group-aware held-out split: per-class metrics, confusion matrix, calibration, abstention, robustness, out-of-scope routing, measured leakage, and a failed acceptance criterion reported as failed | `results.md` section 1, `docs/ml/reports/waste-classification-2.0.0.md` |
| Forecasting and anomaly detection with baselines and no unlabelled claims | `results.md` section 4 |
| Licence discipline: TrashNet and TrashBox removed after audit, RealWaste kept research-only because its licence is contested | `ethics-and-data-statement.md`, `docs/ml/dataset-research/` |
| Verified related-work entries with exact bibliographic data | `literature-survey.md` (20 entries; four have incomplete author lists) |

## 2. What a reviewer would reject today
| # | Gap | Why it matters | Closing action | Who |
|---|---|---|---|---|
| 1 | The classifier has no field evidence and is not approved: 0.895 accuracy on a single Australian facility's held-out photographs, 79.7% of out-of-scope images routed to review (criterion: 90%), no Hyderabad evaluation, no active model, and a training-data licence conflict | the headline AI claim cannot be "accurate waste sorting". The publishable claim is the measured in-domain performance, the leakage and abstention analysis, and the explicit unmet criterion | run the field protocol (`docs/ml/field-evaluation-protocol.md`: at least 300 consented Hyderabad photographs), obtain the RealWaste authors' written licence confirmation, then re-evaluate against the pre-declared criteria | owner |
| 2 | No user study, pilot or field data | usability, adoption and operational benefit are unmeasured | run a small study (for example task-completion with 8 to 12 participants, or a pilot at one ward) with ethics approval | owner |
| 3 | Related work is selective, not a protocol-based search | journals expect database, query strings and inclusion criteria, or an explicit "selective review" statement | run a documented search (for example Scopus, Web of Science, IEEE Xplore) for 2018 to 2026, record it, and complete the four incomplete author lists | authors |
| 4 | Novelty is not established | integrated waste web apps with classifiers already exist (`literature-survey.md` entry 18) | state the contribution as the combination listed under Positioning, and compare with at least three named systems | authors |
| 5 | Ethics, privacy and data-licence statement is a draft | venues require a statement; location of workers and photos are personal data | confirm `ethics-and-data-statement.md`; get the RealWaste licence confirmed in writing; verify the open-data licences of the Austin and Ballarat series | owner |
| 6 | Evidence comes from one sandbox | performance and load were measured on 2 CPU cores with tiny data | repeat the load test on the intended hardware; state hardware in the paper | owner |
| 7 | Integrations unverified against real services | real SMTP, real GPS, real map tiles, Google keys, OSRM were never run | run each once (`docs/project-completion/RELEASE_CHECKLIST.md`) and record results, or keep the paper's claims limited to the simulated ones, as now | owner |
| 8 | No human accessibility or design review | automated axe scans cannot establish WCAG conformance | complete `docs/testing/ACCESSIBILITY_MANUAL_CHECKLIST.md` with a person using a keyboard and a screen reader | owner |
| 9 | Open-release decision | the repository's `LICENSE` says "All rights reserved. No license is granted", so the code is **not** open source and reviewers cannot reuse it; many venues expect code and data availability | choose a code licence (or state in the paper that the code is available on request or under embargo), confirm that no non-commercial-trained artefact is published, add a `CITATION.cff`, and archive a tagged release (for example on Zenodo) for a citable DOI | owner |
| 10 | Forecast and anomaly claims limited | the forecaster beat the naive baseline on 2 of 4 series; anomalies were tested on injected spikes only | keep the claim as "baseline-first tooling"; do not claim detection accuracy | authors |

## 3. Suggested paper
**Type:** system and evaluation paper with an honest, pre-declared acceptance test that the classifier did not pass.
**Working title:** "From citizen report to verified recovery: an auditable municipal waste platform and an honest look at
classifier calibration, abstention and unmet field-acceptance criteria".
**Structure:** (1) problem and gap; (2) related work (`literature-survey.md`); (3) system design: modular monolith, RBAC,
database-enforced audit and custody, retrieval-only assistant (`methodology.md` sections 1 to 8); (4) classifier
pipeline and licence-gated release process; (5) results: RealWaste held-out accuracy 0.895 and macro-F1 0.896, calibration 0.036, 82.9% auto-accepted at 93.5%
accuracy, 79.7% of out-of-scope images to review (criterion not met), leakage study (31.8% near-twins under a naive split
versus 5.8% grouped), robustness table (`results.md`);
(6) forecasting, anomaly and routing results with baselines; (7) engineering evidence (tests, CI, security review);
(8) limitations (`docs/project-completion/LIMITATIONS.md`); (9) ethics and data statement; (10) availability (state the actual licence).

**Claims the evidence supports:** in-domain performance on one dataset with intervals; abstention routes most (79.7%, not the required 90%) out-of-scope inputs to review; group-aware
splits reduce a measurable optimism (they do not remove it); the platform's tests and controls exist and pass.
**Claims the evidence does not support:** field accuracy, better accuracy than published work on TrashNet or RealWaste, operational benefit,
emission savings, real-time tracking in production, accessibility conformance, security certification.

## 4. Candidate venues (not verified; for the authors to check)
Open-access journals that publish applied waste, smart-city and AI-systems work include Sustainability, Sensors, Applied
Sciences and IEEE Access; Journal of Cleaner Production and Waste Management are more selective and expect field evidence.
A software or data paper venue, or a workshop on climate or sustainable computing, fits a system paper with limited field
data better. Read each venue's scope, article charge, preprint policy and AI-disclosure rules before choosing.

## 5. Pre-submission checklist
- [ ] Confirm ethics statement and licence table (owner).
- [ ] Decide the code licence and archive a tagged release with a DOI (owner).
- [ ] Complete bibliographic metadata and run a documented literature search.
- [ ] Re-run the evaluation commands in `ml/README.md` and attach the report hashes.
- [ ] Re-run the full test suites and CI on the exact submitted commit; quote that commit hash.
- [ ] Add figures from `docs/ml/reports/figures/` and real screenshots from `docs/ui/evidence/`.
- [ ] Complete the human accessibility review, or state in the paper that it was not done.
- [ ] Have a person outside the project read the paper and the user manual.
