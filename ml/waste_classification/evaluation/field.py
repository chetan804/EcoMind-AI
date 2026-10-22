"""Field evaluation on locally collected, consented photographs (Hyderabad).

    python -m ml.waste_classification.evaluation.field --manifest PATH.tsv --images DIR

The protocol (permission, consent, privacy, labelling) is `docs/ml/field-evaluation-protocol.md`.
Field photographs are an EVALUATION set only: they are never used for training, tuning or choosing
thresholds. This module refuses a manifest with missing permission/consent/privacy records, with
duplicate or training/prohibited-overlap files, or with too few images, and it writes
`docs/ml/reports/field-evaluation-<version>.json` only from real measurements.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from ml.common.evaluation import metrics as mt
from ml.waste_classification.data import provenance
from ml.waste_classification.data.imagefolder import sha256_bytes
from ml.waste_classification.training.features import REPO, load_config

OUT_OF_SCOPE = "out_of_scope"
REQUIRED_COLUMNS = (
    "file",
    "sha256",
    "class",
    "captured_on",
    "site_id",
    "collector_id",
    "permission_ref",
    "consent_ref",
    "privacy_check",
    "label_checked_by_two",
)
MIN_PER_CLASS = 30  # fewer images per class than this gives a recall estimate too wide to use


class FieldManifestError(ValueError):
    """The field manifest is not acceptable. The message lists every problem."""


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def manifest_problems(
    rows: list[dict[str, str]],
    classes: list[str],
    *,
    min_images: int,
    prohibited: frozenset[str],
    training_hashes: frozenset[str],
) -> list[str]:
    """Every reason this field manifest must be refused (empty list = acceptable)."""
    if not rows:
        return ["the manifest has no rows"]
    problems: list[str] = []
    if missing := [c for c in REQUIRED_COLUMNS if c not in rows[0]]:
        return [f"missing columns: {missing}"]
    seen: set[str] = set()
    for number, row in enumerate(rows, start=2):
        where = f"row {number} ({row.get('file', '?')})"
        if blank := [c for c in REQUIRED_COLUMNS if not (row.get(c) or "").strip()]:
            problems.append(f"{where}: empty {blank}")
            continue
        if row["class"] not in [*classes, OUT_OF_SCOPE]:
            problems.append(f"{where}: unknown class {row['class']!r}")
        digest = row["sha256"].lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            problems.append(f"{where}: malformed sha256")
        if digest in seen:
            problems.append(f"{where}: duplicate file content")
        seen.add(digest)
        if digest in prohibited:
            problems.append(f"{where}: byte-identical to a prohibited (TrashNet) image")
        if digest in training_hashes:
            problems.append(f"{where}: byte-identical to a training image (leakage)")
        if row["privacy_check"].strip().lower() != "yes":
            problems.append(f"{where}: privacy check not confirmed")
        if row["label_checked_by_two"].strip().lower() != "yes":
            problems.append(f"{where}: label not confirmed by two people")
        if row["permission_ref"].strip().lower() in {"none", "n/a", "tbd"}:
            problems.append(f"{where}: no permission record")
    in_scope = Counter(r["class"] for r in rows if r["class"] in classes)
    if sum(in_scope.values()) < min_images:
        problems.append(f"{sum(in_scope.values())} in-scope images, at least {min_images} needed")
    for name in classes:
        if in_scope[name] < MIN_PER_CLASS:
            problems.append(
                f"class {name!r} has {in_scope[name]} images, at least {MIN_PER_CLASS} needed"
            )
    return problems


def summarise(
    truth: list[str], predicted: list[str], needs_review: list[bool], classes: list[str]
) -> dict[str, Any]:
    """Field metrics from in-scope truth/prediction pairs (pure; unit-tested)."""
    index = {c: i for i, c in enumerate(classes)}
    y = np.array([index[t] for t in truth])
    p = np.array([index[x] for x in predicted])
    matrix = mt.confusion_matrix(y, p, len(classes))
    accepted = ~np.array(needs_review)
    n_acc = int(accepted.sum())
    correct = y == p
    low, high = mt.wilson_interval(int(correct[accepted].sum()), n_acc)
    return {
        "n_images": len(truth),
        "accuracy": mt.accuracy(y, p),
        "macro_f1": mt.macro_f1(y, p, len(classes)),
        "per_class": [
            {"class": c, **vars(r)}
            for c, r in zip(classes, mt.per_class_report(matrix), strict=True)
        ],
        "confusion_matrix": matrix.tolist(),
        "auto_accept_rate": float(accepted.mean()),
        "accuracy_of_auto_accepted": float(correct[accepted].mean()) if n_acc else 0.0,
        "accuracy_of_auto_accepted_ci95": [low, high],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    args = parser.parse_args(argv)

    from ml.waste_classification.inference.classifier import WasteClassifier

    config = load_config()
    classes: list[str] = config["dataset"]["classes"]
    version = config["version"]
    artifact = REPO / "ml" / "artifacts" / "waste_classification" / version
    training_table = REPO / config["dataset"]["per_file_table"]
    training_hashes = frozenset(
        line.split("\t")[1] for line in training_table.read_text().splitlines()[1:] if line
    )
    rows = read_manifest(args.manifest)
    problems = manifest_problems(
        rows,
        classes,
        min_images=config["acceptance"]["field"]["min_images"],
        prohibited=provenance.load_denylist(REPO / config["dataset"]["denylist"]),
        training_hashes=training_hashes,
    )
    if problems:
        raise FieldManifestError("field manifest refused:\n  - " + "\n  - ".join(problems))

    clf = WasteClassifier.load(artifact, REPO / "ml" / "artifacts" / "_backbones")
    truth: list[str] = []
    predicted: list[str] = []
    review: list[bool] = []
    out_flags: list[bool] = []
    for row in rows:
        data = (args.images / row["file"]).read_bytes()
        if sha256_bytes(data) != row["sha256"].lower():
            raise FieldManifestError(f"{row['file']} does not match its recorded sha256")
        prediction = clf.predict_bytes(data)
        if row["class"] == OUT_OF_SCOPE:
            out_flags.append(prediction.needs_review)
        else:
            truth.append(row["class"])
            predicted.append(prediction.label)
            review.append(prediction.needs_review)
    report = summarise(truth, predicted, review, classes)
    report.update(
        model_version=version,
        model_files=json.loads((artifact / "model.json").read_text())["files"],
        manifest_sha256=sha256_bytes(args.manifest.read_bytes()),
        n_out_of_scope=len(out_flags),
        out_of_scope_sent_to_review=float(np.mean(out_flags)) if out_flags else None,
        sites=sorted({r["site_id"] for r in rows}),
        captured_between=[min(r["captured_on"] for r in rows), max(r["captured_on"] for r in rows)],
    )
    out = REPO / "docs" / "ml" / "reports" / f"field-evaluation-{version}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"wrote {out}: {report['n_images']} images, macro-F1 {report['macro_f1']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
