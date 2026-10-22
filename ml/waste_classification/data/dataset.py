"""Load the configured dataset through the provenance gate (the only way training reads images)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ml.waste_classification.data import provenance
from ml.waste_classification.data.imagefolder import (
    Sample,
    files_digest,
    list_folder,
    list_out_of_scope,
    list_samples,
    sha256_bytes,
)

REPO = provenance.REPO


@dataclass(frozen=True)
class VerifiedDataset:
    manifest: dict[str, Any]
    label_map: dict[str, str | None]
    samples: list[Sample]  # in scope: used for training, validation and test
    out_of_scope: list[tuple[str, Path]]  # no EcoMind class: review-routing evaluation only
    every_file: list[Sample]
    file_hash: dict[str, str]  # key -> sha256
    digest: str


def load_verified(config: dict[str, Any], *, hash_files: bool = True) -> VerifiedDataset:
    """Validate provenance, then list and hash the files. Raises `ProvenanceError` on any problem.

    Order matters: the manifest is checked before the directory is touched, the denylist before any
    image is decoded, and the content digest before anything is returned.
    """
    cfg = config["dataset"]
    manifest = provenance.load_manifest(REPO / cfg["manifest"])
    provenance.require_acceptable(manifest)
    denylist = provenance.load_denylist(REPO / cfg["denylist"])  # missing/empty denylist: refuse
    root = REPO / cfg["root"]
    if not root.is_dir():
        raise provenance.ProvenanceError(
            f"dataset directory {root} is missing: run ml.waste_classification.data.fetch"
        )
    label_map = provenance.label_map(manifest)
    samples = list_samples(root, label_map, cfg["classes"])
    out_of_scope = list_out_of_scope(root, label_map)
    every_file = [
        Sample(path, folder.name, -1)
        for folder in sorted(p for p in root.iterdir() if p.is_dir())
        for path in list_folder(folder)
    ]
    if len(every_file) != manifest["images"]["total"]:
        raise provenance.ProvenanceError("dataset file count differs from the manifest")
    file_hash = {f.key: sha256_bytes(f.path.read_bytes()) for f in every_file} if hash_files else {}
    if hash_files:
        provenance.require_no_prohibited_files(file_hash, denylist)
        if files_digest(every_file) != manifest["images"]["files_digest"]:
            raise provenance.ProvenanceError("dataset content differs from the manifest digest")
    return VerifiedDataset(
        manifest=manifest,
        label_map=label_map,
        samples=samples,
        out_of_scope=out_of_scope,
        every_file=every_file,
        file_hash=file_hash,
        digest=manifest["images"]["files_digest"] if hash_files else "",
    )
