# Literature and source survey

Scope: a short, **verified** survey. Each entry below was looked up (entries 1 to 7 on 2026-10-20, entries 8 to 20
on 2026-10-22; the page or catalogue where it was found is given) and is cited only for what that source states.
This is deliberately not an exhaustive review: it was built from targeted searches, not from a protocol such as
PRISMA, so it supports the positioning section below but cannot establish that no similar system exists. No
reference is included that could not be checked. Where a page showed only part of the bibliographic data
(for example no author list), only that part is given.

## Waste-image datasets and benchmarks

1. **Thung, G. and Yang, M. (2016). *Classification of Trash for Recyclability Status.* CS229 project
   report, Stanford University.** <https://cs229.stanford.edu/proj2016/report/ThungYang-ClassificationOfTrashForRecyclabilityStatus-report.pdf>.
   Introduces the six-class (glass, paper, metal, plastic, cardboard, trash) hand-collected image dataset
   later distributed as TrashNet, and compares SVM-with-SIFT and a CNN. The repository
   `garythung/trashnet` carries an MIT licence file, but the project has **no written permission covering the
   photographs themselves**, so TrashNet is **excluded from every training, validation, test and release dataset**
   (2026-10-22). *Use in this project:* cited as background only; its 2,524 file hashes are kept in a denylist so
   that no copy of it, including the 819 byte-identical files in TrashBox, can enter a dataset. *Limitation noted
   by others and observed here:* photographs of single items on a plain background, unlike field images.
2. **Single, S., Iranmanesh, S. and Raad, R. (2023). RealWaste: A Novel Real-Life Data Set for Landfill Waste
   Classification Using Deep Learning. *Information* 14(12):633.** DOI 10.3390/info14120633
   <https://doi.org/10.3390/info14120633>; dataset UCI id 908, DOI 10.24432/C5SS4G. 4,752 photographs in nine
   classes taken at a landfill near Wollongong, Australia (University of Wollongong); the authors' best reported
   result is 89.19% (Inception V3, their own split). **Licence conflict:** the UCI page states CC BY 4.0; the authors'
   GitHub README states CC BY-NC-SA 4.0. *Use:* the only training dataset of the current research candidate
   (`waste-classification 2.0.0`), treated as research-only until the authors confirm the licence in writing.
3. **Proença, P. F. and Simões, P. (2020). TACO: Trash Annotations in Context for Litter Detection.
   arXiv:2003.06975.** <https://arxiv.org/abs/2003.06975>. An open litter detection and segmentation
   dataset (1,500 images and 4,784 annotations in the paper's version) with a 60-category hierarchical
   taxonomy. *Use:* catalogued and **not ingested**: its labels are segmentation/detection labels and the
   images are hosted per-photo on a service this sandbox cannot reach (see
   `docs/ml/dataset-research/REJECTED_DATASETS.md`).
4. **TrashBox** (`nikhilvenkatkumsetty/TrashBox`; README cites IEEE FRUCT'31, IEEE Xplore 9770922).
   Seven classes including e-waste and medical waste. *Use:* **prohibited and not used.** The repository carries no
   licence, its README counts disagree with its folders, and 819 of its files are byte-identical to TrashNet
   images. An earlier research experiment on it was withdrawn on 2026-10-22. The paper itself was not read.

## Methods used

5. **Guo, C., Pleiss, G., Sun, Y. and Weinberger, K. Q. (2017). On Calibration of Modern Neural Networks.
   *Proceedings of the 34th International Conference on Machine Learning*, PMLR 70:1321–1330.**
   <https://proceedings.mlr.press/v70/guo17a.html>. Shows that a single-parameter temperature scaling,
   fitted on a validation set, calibrates predictions without changing accuracy. *Use:* the classifier's
   confidence is temperature-scaled on the validation split, and expected calibration error is reported.
6. **Hyndman, R. J. and Athanasopoulos, G. (2021). *Forecasting: Principles and Practice*, 3rd edition.
   OTexts, Melbourne.** <https://otexts.com/fpp3/>. Reference for Holt-Winters exponential smoothing,
   naive baselines and evaluating forecasts against them. *Use:* the forecaster is judged against a
   seasonal-naive/naive baseline, never alone.
7. **Held, M. and Karp, R. M. (1962). A dynamic programming approach to sequencing problems. *Journal of the
   Society for Industrial and Applied Mathematics* 10(1):196–210. DOI 10.1137/0110015.**
   The exact dynamic-programming recursion for the travelling-salesman problem. *Use:* the route optimiser is
   exact (Held-Karp) up to 12 stops.

## Surveys and recent field evidence (added 2026-10-22)

8. **Fotovvatikhah, F., Ahmedy, I., Md Noor, R. and Munir, M. U. (2025). A Systematic Review of AI-Based
   Techniques for Automated Waste Classification. *Sensors* 25(10):3181.** DOI 10.3390/s25103181
   <https://www.mdpi.com/1424-8220/25/10/3181>. A systematic review (Kitchenham and PRISMA guidelines) of more
   than 97 studies and more than fifteen public waste-classification datasets; it names dataset imbalance,
   real-world variability and lack of standardisation as key limitations. *Use:* background for the dataset
   limits this project measured itself.
9. **Echchidmi, M. and Bouayad, A. (2026). Compact waste image classification with multi-student CNNs and
   edge-oriented model selection. *Frontiers in Artificial Intelligence* 9:1804734.** DOI
   10.3389/frai.2026.1804734 <https://pmc.ncbi.nlm.nih.gov/articles/PMC13366473/>. Reports 94.18% top-1 accuracy
   for a compact student model on TrashNet and, evaluated zero-shot on the six RealWaste classes that overlap
   with TrashNet, 41.04% accuracy (macro-F1 0.3648), and attributes the gap to the controlled TrashNet
   background versus cluttered landfill images. *Use:* independent evidence that benchmark
   accuracy overstates field accuracy. This project's own measurement of that gap was withdrawn with the TrashNet
   model, so it now relies on this entry and on a field evaluation it has not yet run.
10. **Ijaz, M. et al. (2026). GlobalWasteData: A Large-Scale, Integrated Dataset for Robust Waste Classification
    and Environmental Monitoring. arXiv:2602.07463** (submitted 7 February 2026; preprint, not peer reviewed as
    far as this survey could verify). <https://arxiv.org/abs/2602.07463>. Merges public datasets into one
    archive of 89,807 images in 14 categories with 68 subclasses. *Use:* shows the field is moving toward merged
    datasets. *Not used:* the licences of the merged sources were not checked here, so the archive is not a
    permitted training source for this project (see the licence rules in `DECISION_LOG.md`).
11. **Olawade, D. B. et al. (2024). Smart waste management: A paradigm shift enabled by artificial intelligence.
    *Waste Management Bulletin* 2(5).** DOI 10.1016/j.wmb.2024.05.001 (open access, CC BY-NC-ND 4.0 per the
    copy found at ResearchGate; only the first author's name was recorded). *Use:* an AI-in-waste-management
    overview for context.
12. **Xia, W., Jiang, Y., Chen, X. and Zhao, R. (2022). Application of machine learning algorithms in municipal
    solid waste management: A mini review.** SAGE journals, DOI 10.1177/0734242X211033716
    <https://journals.sagepub.com/doi/10.1177/0734242X211033716>. Tabulates waste-generation prediction
    studies (for example gradient-boosted trees and neural networks on weekly or yearly series). *Use:* the
    forecasting literature this project does **not** attempt to beat; the project's forecaster is a baseline-first
    statistical tool (`methodology.md`, section 4).
13. **A systematic literature review on municipal solid waste management using machine learning and deep
    learning. *Artificial Intelligence Review* (2025).** DOI 10.1007/s10462-025-11196-9
    <https://link.springer.com/article/10.1007/s10462-025-11196-9> (author list not recorded). Reviews 69
    studies from 2018 to 2024 with PRISMA; reports random forest as the most used technique and data
    availability and quality as the main obstacles. *Use:* context for the data limits stated in the results.
14. **Beliën, J., De Boeck, L. and Van Ackere, J. (2014). Municipal solid waste collection and management
    problems: a literature review. *Transportation Science* 48(1):78–102.** DOI 10.1287/trsc.1120.0448
    <https://pubsonline.informs.org/doi/10.1287/trsc.1120.0448>. A classified review of waste-collection
    vehicle-routing problems. *Use:* shows the project's straight-line, single-vehicle ordering is a small
    special case; time windows, capacities and multi-vehicle routing are the standard research problems that
    are **not** implemented here.

## Abstention and calibration

15. **Hendrycks, D. and Gimpel, K. (2017). A Baseline for Detecting Misclassified and Out-of-Distribution
    Examples in Neural Networks. ICLR 2017. arXiv:1610.02136.** <https://arxiv.org/abs/1610.02136>. Shows that
    the maximum softmax probability tends to be lower for misclassified and out-of-distribution examples and
    is a usable detection baseline, while sometimes ineffective. *Use:* motivates routing low-confidence
    inputs to review; the project adds a feature-similarity (novelty) check because confidence alone is not a
    reliable guard against unfamiliar inputs (the novelty gate is evaluated on the out-of-scope RealWaste folders).
16. **Geifman, Y. and El-Yaniv, R. (2017). Selective Classification for Deep Neural Networks. arXiv:1705.08500
    (NeurIPS 2017).** <https://arxiv.org/abs/1705.08500>. Formalises a classifier that may abstain, trading
    coverage for risk. *Use:* the project reports coverage and accuracy of accepted predictions together
    (2.0.0 on the held-out test split: 82.9% coverage, 93.5% accuracy of accepted predictions), which is the selective-classification view. The project does
    not provide the risk guarantee of that paper's method.

## Related systems

17. **IoT-driven smart waste management with software-engineering integration. *Sustainability* 17(21):9803
    (2025).** DOI 10.3390/su17219803 <https://doi.org/10.3390/su17219803> (authors not recorded). A system with
    bin-level sensing, a mobile app and a cloud back end. *Contrast:* this project has no sensor hardware and
    deliberately keeps telemetry out of the product.
18. **Smart Recycling Assistant: An Integrated AI-Powered Waste Classification and Management System. Springer
    chapter.** DOI 10.1007/978-3-032-04539-3_42 <https://link.springer.com/chapter/10.1007/978-3-032-04539-3_42>
    (authors not recorded). A web application combining a classifier, user feedback and location-based
    recommendations. *Contrast:* shows that a web front end plus a classifier is already common; this project's
    contribution (see Positioning below) cannot rest on that alone.

## Standards used by the engineering

19. **M'Raihi, D., Machani, S., Pei, M. and Rydell, J. (2011). TOTP: Time-Based One-Time Password Algorithm.
    RFC 6238 (Informational).** <https://www.rfc-editor.org/info/rfc6238>. *Use:* the two-step verification
    algorithm; the repository's tests include a published test vector.
20. **W3C (2024). Web Content Accessibility Guidelines (WCAG) 2.2. W3C Recommendation, 12 December 2024.**
    <https://www.w3.org/TR/WCAG22/>. *Use:* the success criteria that the automated axe checks target; the
    document itself says conformance cannot be established by tools alone.

## Positioning (what this survey supports, and what it does not)

* **Supported:** a benchmark-to-field accuracy gap for TrashNet-trained classifiers is reported by others
  (entry 9; this project has no measurement of its own, because its TrashNet model was withdrawn); merged and larger datasets exist but raise licence questions (entries 8 and 10); abstention
  is an established idea (entries 15 and 16); integrated web systems with classifiers already exist
  (entries 17 and 18).
* **Candidate contributions, to be argued in a paper:** an audited reference implementation (the code is currently all-rights-reserved, so "open" cannot be claimed) that connects
  a citizen report to a verified recovery record; evaluation that reports out-of-distribution accuracy,
  calibration and the review-routing rate next to in-domain accuracy; a licence-gated model release process;
  database-enforced append-only audit and custody records; a retrieval-only assistant whose answers are
  traceable to articles. Whether each is novel relative to the literature has **not** been established by this
  survey.
* **Not supported:** any claim that the classifier is accurate in the field, any claim of better accuracy than
  published results on TrashNet or RealWaste (different protocol, frozen backbone, single seed), any claim about forecasting or routing
  performance relative to the literature.

## Gaps this survey does not fill
- A protocol-based literature search (databases, query strings, inclusion criteria, dates) has not been done.
  A paper submitted to a journal needs one, or an explicit statement that the related work is selective.
- Waste-generation forecasting and collection-routing literature are represented only by one review each
  (entries 12 and 14); no study was read in detail, and the project makes no claim about how it compares.
- The routing validation dataset (Kalasin University campus, Thailand, CC BY 4.0 as recorded) and the municipal-waste reference series
  are documented in `docs/ml/dataset-research/DATASET_CATALOG.md` with their access dates; their original
  papers were not retrieved, so none is cited here.
- Entries 11, 13, 17 and 18 have incomplete author lists because the pages consulted did not show them; complete
  the metadata from the publisher pages before submission.
