"""Fetch and verify the external inputs of the waste classifier (all git-ignored).

    python -m ml.waste_classification.data.fetch

Everything is pinned to a commit and verified against a SHA-256, so a changed upstream cannot
silently change an experiment. Needs ``git`` and network access to github.com.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ml.waste_classification.data.trashnet import extract_dataset
from ml.waste_classification.inference.embedder import sha256_file

REPO = Path(__file__).resolve().parents[3]
TRASHNET = {
    "url": "https://github.com/garythung/trashnet",
    "commit": "6fa2b878c6c1b4304b91109070ce0edf9279bb31",
    "zip_sha256": "0bf472790f8b20e5c950d5b5012a9d38af0d3392efd65f8ce171334fc16b07c2",
}
CORAL = {
    "url": "https://github.com/google-coral/test_data",
    "commit": "104342d2d3480b3e66203073dac24f4e2dbb4c41",
}
BACKBONE_FILES = [
    "efficientnet-edgetpu-S_quant_embedding_extractor.tflite",
    "efficientnet-edgetpu-M_quant_embedding_extractor.tflite",
    "efficientnet-edgetpu-L_quant_embedding_extractor.tflite",
]
OOD_FILES = ["cat.bmp", "parrot.jpg", "bird.bmp", "grace_hopper.bmp", "checker224X224.bmp"]


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)  # noqa: S603, S607


def _checkout(url: str, commit: str, target: Path, paths: list[str] | None) -> None:
    if target.exists():
        shutil.rmtree(target)
    _git("clone", "--filter=blob:none", "--no-checkout", url, str(target))
    if paths:
        _git("sparse-checkout", "set", "--no-cone", *paths, cwd=target)
    _git("checkout", commit, cwd=target)


def main() -> int:
    external = REPO / "datasets" / "external"
    source = external / "trashnet-src"
    if not (source / "data" / "dataset-resized.zip").exists():
        _checkout(
            TRASHNET["url"], TRASHNET["commit"], source, ["data/dataset-resized.zip", "LICENSE"]
        )
    archive = source / "data" / "dataset-resized.zip"
    if sha256_file(archive) != TRASHNET["zip_sha256"]:
        print("TrashNet archive hash mismatch", file=sys.stderr)
        return 1
    if not (external / "trashnet" / "dataset-resized").exists():
        extract_dataset(archive, external / "trashnet")

    backbones = REPO / "ml" / "artifacts" / "_backbones"
    ood = backbones.parent / "_ood"
    if not all((backbones / n).exists() for n in BACKBONE_FILES) or not all(
        (ood / n).exists() for n in OOD_FILES
    ):
        scratch = external / "coral-src"
        _checkout(CORAL["url"], CORAL["commit"], scratch, [*BACKBONE_FILES, *OOD_FILES, "LICENSE"])
        backbones.mkdir(parents=True, exist_ok=True)
        for name in BACKBONE_FILES:
            shutil.copy2(scratch / name, backbones / name)
        ood.mkdir(parents=True, exist_ok=True)
        for name in OOD_FILES:
            shutil.copy2(scratch / name, ood / name)
        shutil.copy2(scratch / "LICENSE", backbones / "LICENSE.coral-test-data")
    print("datasets and backbones ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
