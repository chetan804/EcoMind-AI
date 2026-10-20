# Literature and source survey

Scope: a short, **verified** survey. Each entry below was looked up on 2026-10-20 (the location where it
was found is given) and is cited only for what that source states. This is deliberately not an exhaustive
review; a full review needs a library search that this project has not done. No reference is included that
could not be checked.

## Waste-image datasets and benchmarks

1. **Thung, G. and Yang, M. (2016). *Classification of Trash for Recyclability Status.* CS229 project
   report, Stanford University.** <https://cs229.stanford.edu/proj2016/report/ThungYang-ClassificationOfTrashForRecyclabilityStatus-report.pdf>.
   Introduces the six-class (glass, paper, metal, plastic, cardboard, trash) hand-collected image dataset
   later distributed as TrashNet, and compares SVM-with-SIFT and a CNN. The repository
   `garythung/trashnet` (MIT) is the data source used here (2,527 images in the distributed archive).
   *Use in this project:* training and held-out evaluation of the baseline classifier. *Limitation noted by
   the project:* photographs of single items on a plain background, unlike field images.
2. **Single, S. et al. (2023). RealWaste. *Information* 14(12):633.** (Title as
   recorded in the dataset README; the full subtitle was not verified.) <https://www.mdpi.com/2078-2489/14/12/633>
   (citation as given in the dataset's README at `sam-single/realwaste`; the paper page itself was not opened, so
   only the first author is named). 4,752 photographs in nine classes from a waste
   facility near Wollongong, Australia, licensed CC BY-NC-SA 4.0 per the README. *Use:* cross-dataset evaluation and an
   experiment-only multi-dataset study; non-commercial terms mean no model trained on it is released.
3. **Proença, P. F. and Simões, P. (2020). TACO: Trash Annotations in Context for Litter Detection.
   arXiv:2003.06975.** <https://arxiv.org/abs/2003.06975>. An open litter detection and segmentation
   dataset (1,500 images and 4,784 annotations in the paper's version) with a 60-category hierarchical
   taxonomy. *Use:* catalogued and **not ingested**: its labels are segmentation/detection labels and the
   images are hosted per-photo on a service this sandbox cannot reach (see
   `docs/ml/dataset-research/REJECTED_DATASETS.md`).
4. **TrashBox** (`nikhilvenkatkumsetty/TrashBox`; README cites IEEE FRUCT'31, IEEE Xplore 9770922).
   Seven classes including e-waste and medical waste. *Use:* catalogued and **not used**, because the
   repository carries no licence and its README counts disagree with its folders. The paper itself was not
   read.

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

## Gaps this survey does not fill
- Published accuracy of waste classifiers on field data, municipal fill-level forecasting studies, and
  collection-routing literature (vehicle-routing variants, time windows) have **not** been surveyed with
  verified citations; the project makes no claim about how it compares with them.
- The routing validation dataset (King Saud University, CC BY 4.0) and the municipal-waste reference series
  are documented in `docs/ml/dataset-research/DATASET_CATALOG.md` with their access dates; their original
  papers were not retrieved, so none is cited here.
