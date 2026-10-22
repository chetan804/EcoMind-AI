# Paper readiness (as of 2026-10-22)

**Verdict: the software and documents are ready for a project report and a supervised demonstration. They are not yet
sufficient for a peer-reviewed research paper.** This file lists what a reviewer would accept, what they would object
to, and the owner-only actions that close each gap. Nothing here is a claim about acceptance by any venue; venue scope,
fees and AI-disclosure rules were not verified and must be read on the venue's own site.

## 1. What is solid enough to report
| Item | Evidence |
|---|---|
| A working, tested, audited platform from report to verified recovery | 787 backend, 386 frontend, 61 ML, 147 contract and 61 browser tests (`results.md` section 6); CI green on `main` |
| Reproducible classifier pipeline with committed hashes | retrained on 2026-10-21 with identical accuracy, macro-F1, calibration error and weight hashes |
| Honest evaluation: in-domain, cross-dataset, calibration, abstention, robustness, leakage | `results.md` sections 1 and 2 |
| Forecasting and anomaly detection with baselines and no unlabelled claims | `results.md` section 4 |
| Licence discipline, with every dataset audited and the unreleasable ones kept out of the model | `ethics-and-data-statement.md`, `docs/ml/dataset-research/` |
| Verified related-work entries with exact bibliographic data | `literature-survey.md` (20 entries; four have incomplete author lists) |

## 2. What a reviewer would reject today
| # | Gap | Why it matters | Closing action | Who |
|---|---|---|---|---|
| 1 | The classifier is below field quality: 0.454 accuracy on real facility photos, no approved or active model | the headline AI claim cannot be "accurate waste sorting". The publishable claim is the measured gap and the abstention design | either report it as a negative-result and system paper (recommended), or obtain licence-clean field images (own photographs with consent, or a dataset with a commercial-compatible licence) and fine-tune | owner |
| 2 | No user study, pilot or field data | usability, adoption and operational benefit are unmeasured | run a small study (for example task-completion with 8 to 12 participants, or a pilot at one ward) with ethics approval | owner |
| 3 | Related work is selective, not a protocol-based search | journals expect database, query strings and inclusion criteria, or an explicit "selective review" statement | run a documented search (for example Scopus, Web of Science, IEEE Xplore) for 2018 to 2026, record it, and complete the four incomplete author lists | authors |
| 4 | Novelty is not established | integrated waste web apps with classifiers already exist (`literature-survey.md` entry 18) | state the contribution as the combination listed under Positioning, and compare with at least three named systems | authors |
| 5 | Ethics, privacy and data-licence statement is a draft | venues require a statement; location of workers and photos are personal data | confirm `ethics-and-data-statement.md`; get TrashBox permission in writing; verify the open-data licences of the Austin and Ballarat series | owner |
| 6 | Evidence comes from one sandbox | performance and load were measured on 2 CPU cores with tiny data | repeat the load test on the intended hardware; state hardware in the paper | owner |
| 7 | Integrations unverified against real services | real SMTP, real GPS, real map tiles, Google keys, OSRM were never run | run each once (`docs/project-completion/RELEASE_CHECKLIST.md`) and record results, or keep the paper's claims limited to the simulated ones, as now | owner |
| 8 | No human accessibility or design review | automated axe scans cannot establish WCAG conformance | complete `docs/testing/ACCESSIBILITY_MANUAL_CHECKLIST.md` with a person using a keyboard and a screen reader | owner |
| 9 | Open-release decision | the repository's `LICENSE` says "All rights reserved. No license is granted", so the code is **not** open source and reviewers cannot reuse it; many venues expect code and data availability | choose a code licence (or state in the paper that the code is available on request or under embargo), confirm that no non-commercial-trained artefact is published, add a `CITATION.cff`, and archive a tagged release (for example on Zenodo) for a citable DOI | owner |
| 10 | Forecast and anomaly claims limited | the forecaster beat the naive baseline on 2 of 4 series; anomalies were tested on injected spikes only | keep the claim as "baseline-first tooling"; do not claim detection accuracy | authors |

## 3. Suggested paper
**Type:** system and evaluation paper with an honest negative result on distribution shift.
**Working title:** "From citizen report to verified recovery: an auditable municipal waste platform and an honest look at
classifier transfer, calibration and abstention".
**Structure:** (1) problem and gap; (2) related work (`literature-survey.md`); (3) system design: modular monolith, RBAC,
database-enforced audit and custody, retrieval-only assistant (`methodology.md` sections 1 to 8); (4) classifier
pipeline and licence-gated release process; (5) results: TrashNet 0.867 versus RealWaste 0.454, calibration 0.031 versus
0.263, 95.5% of out-of-scope images to review, leakage study 0.893 versus 0.867, robustness table (`results.md`);
(6) forecasting, anomaly and routing results with baselines; (7) engineering evidence (tests, CI, security review);
(8) limitations (`docs/project-completion/LIMITATIONS.md`); (9) ethics and data statement; (10) availability (state the actual licence).

**Claims the evidence supports:** the gap and its size; abstention routes most out-of-scope inputs to review; group-aware
splits remove a measurable optimism; the platform's tests and controls exist and pass.
**Claims the evidence does not support:** field accuracy, better accuracy than published TrashNet work, operational benefit,
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
