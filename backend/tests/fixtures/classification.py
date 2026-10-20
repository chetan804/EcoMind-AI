"""Test support for classification: a fake runtime and structurally valid artifacts.

The artifacts have no TFLite backbone (``backbones: []``), so they load and verify like real ones
but cannot embed images; inference itself is faked. The real model is covered by the parity test.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.modules.classification.constants import ModelVersionStatus
from app.modules.classification.models import ClassificationModelVersion
from app.modules.classification.runtime import RawPrediction

CLASSES = ["cardboard", "glass", "metal", "paper", "plastic", "trash"]
MODEL_NAME = "waste-material-classifier"


def confident(label: str = "plastic", confidence: float = 0.93) -> RawPrediction:
    rest = (1 - confidence) / (len(CLASSES) - 1)
    return RawPrediction(
        label=label,
        confidence=confidence,
        probabilities={c: (confidence if c == label else rest) for c in CLASSES},
        needs_review=False,
        review_reasons=[],
        novelty_similarity=0.81,
        inference_ms=12.3,
    )


def unsure(label: str = "glass") -> RawPrediction:
    base = confident(label, 0.55)
    return RawPrediction(
        label=base.label,
        confidence=base.confidence,
        probabilities=base.probabilities,
        needs_review=True,
        review_reasons=["low_confidence"],
        novelty_similarity=0.74,
        inference_ms=11.0,
    )


class FakeRuntime:
    def __init__(
        self, script: Callable[[bytes], RawPrediction], codes: dict[str, str] | None = None
    ) -> None:
        self.manifest: dict[str, Any] = {
            "material_category_codes": codes or {c: c for c in CLASSES}
        }
        self.script = script
        self.calls = 0

    def predict_bytes(self, data: bytes) -> RawPrediction:
        self.calls += 1
        return self.script(data)


class FakeProvider:
    def __init__(self, runtime: FakeRuntime | None = None) -> None:
        self.runtime = runtime or FakeRuntime(lambda _data: confident())

    def runtime_for(self, version: object, artifacts_dir: Path) -> FakeRuntime:
        return self.runtime


def write_artifact(
    artifacts_dir: Path, version: str, *, name: str = MODEL_NAME, min_confidence: float = 0.8
) -> Path:
    """A loadable artifact with correct hashes under ``<dir>/waste_classification/<version>``."""
    directory = artifacts_dir / "waste_classification" / version
    directory.mkdir(parents=True, exist_ok=True)
    np.savez(
        directory / "head.npz",
        coef=np.zeros((len(CLASSES), 4), np.float32),
        intercept=np.zeros(len(CLASSES), np.float32),
    )
    np.save(directory / "novelty_reference.npy", np.zeros((1, 4), np.float16))
    files = {
        n: hashlib.sha256((directory / n).read_bytes()).hexdigest()
        for n in ("head.npz", "novelty_reference.npy")
    }
    manifest = {
        "name": name,
        "version": version,
        "classes": CLASSES,
        "backbones": [],
        "tta_variants": ["identity"],
        "temperature": 1.0,
        "review": {"min_confidence": min_confidence, "min_novelty_similarity": 0.5},
        "files": files,
        "material_category_codes": {c: c for c in CLASSES},
        "trained_at_utc": "2026-10-20T09:30:00Z",
        "evaluation": {"accuracy": 0.867, "macro_f1": 0.841, "n_test": 421},
    }
    (directory / "model.json").write_text(json.dumps(manifest, indent=2))
    return directory


def add_model_version(
    engine: Engine,
    *,
    version: str = "1.0.0",
    status: ModelVersionStatus = ModelVersionStatus.ACTIVE,
    sha256: str | None = "0" * 64,
) -> uuid.UUID:
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        row = ClassificationModelVersion(
            name=MODEL_NAME,
            version=version,
            status=status,
            framework="tflite backbone + numpy linear head",
            artifact_manifest_sha256=sha256,
            evaluation_metrics={"accuracy": 0.867},
        )
        session.add(row)
        session.commit()
        return row.id
