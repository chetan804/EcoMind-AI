"""WITHDRAWN: TrashBox experiment.

It trained on TrashBox, which republished TrashNet (819 identical files) with no licence.
TrashNet and TrashBox are excluded from every new training, validation,
test and release dataset (written permission for the photographs was not obtained),
so the code was removed and this module only refuses to run. The recorded result is
kept as history, marked withdrawn:
  docs/ml/dataset-research/experiments/trashbox-experiment.json
The code is in Git history. The current pipeline is
`ml.waste_classification.training.train` (RealWaste, provenance-gated).
"""

from __future__ import annotations

from typing import NoReturn

WITHDRAWN = True


def main(argv: list[str] | None = None) -> NoReturn:
    raise SystemExit(
        "trashbox_experiment is withdrawn: it used TrashNet/TrashBox, which are excluded from all "
        "datasets. See docs/ml/dataset-research/REJECTED_DATASETS.md."
    )


if __name__ == "__main__":
    main()
