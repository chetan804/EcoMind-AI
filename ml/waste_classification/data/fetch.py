"""Fetch and verify the external inputs of the waste classifier (all git-ignored).

    python -m ml.waste_classification.data.fetch

Everything is pinned to a commit and verified against a SHA-256, so a changed upstream cannot
silently change an experiment. Needs ``git`` and network access to github.com.

TrashNet and TrashBox are deliberately NOT fetched: they are excluded from every new run (see
``provenance.py``). The training dataset is RealWaste (``datasets/manifests/realwaste-2.0.yaml``);
its licence status is *conflicting*, so a model trained on it is research-only.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ml.waste_classification.data import provenance
from ml.waste_classification.data.imagefolder import Sample, files_digest, list_folder

REPO = Path(__file__).resolve().parents[3]
REALWASTE_MANIFEST = REPO / "datasets" / "manifests" / "realwaste-2.0.yaml"
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


def fetch_realwaste(manifest: dict, external: Path) -> Path:  # type: ignore[type-arg]
    """Clone the pinned RealWaste commit and verify every file against the manifest digest."""
    source = external / "realwaste-src"
    root = source / "RealWaste"
    if not root.is_dir():
        if source.exists():
            shutil.rmtree(source)
        source.mkdir(parents=True)
        _git("init", "-q", cwd=source)
        _git("remote", "add", "origin", manifest["source"]["mirror_url"] + ".git", cwd=source)
        _git("fetch", "--depth", "1", "origin", manifest["source"]["commit"], cwd=source)
        _git("checkout", "-q", "FETCH_HEAD", cwd=source)
    everything = [
        Sample(path, folder.name, -1)
        for folder in sorted(p for p in root.iterdir() if p.is_dir())
        for path in list_folder(folder)
    ]
    if len(everything) != manifest["images"]["total"]:
        raise SystemExit(
            f"RealWaste has {len(everything)} images, manifest says {manifest['images']['total']}"
        )
    if files_digest(everything) != manifest["images"]["files_digest"]:
        raise SystemExit("RealWaste content differs from the pinned manifest digest")
    return root


def main() -> int:
    external = REPO / "datasets" / "external"
    manifest = provenance.load_manifest(REALWASTE_MANIFEST)
    provenance.require_acceptable(manifest)  # fail closed before anything is downloaded
    fetch_realwaste(manifest, external)

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
    print("RealWaste (verified) and backbones ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
