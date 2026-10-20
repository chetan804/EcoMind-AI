"""Process-wide cache of the loaded runtime for the active model version.

Loading verifies every artifact hash (see ``ClassifierRuntime.load``) and is done once per
(version, manifest hash); a different active version or a changed ``model.json`` reloads.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Protocol

from app.modules.classification.errors import ModelUnavailableError
from app.modules.classification.models import ClassificationModelVersion
from app.modules.classification.runtime import ClassifierRuntime, sha256_file

CAPABILITY_DIR = "waste_classification"  # <MODEL_ARTIFACTS_DIR>/waste_classification/<version>/
BACKBONE_DIR = "_backbones"  # <MODEL_ARTIFACTS_DIR>/_backbones/*.tflite


class RuntimeProvider(Protocol):
    def runtime_for(
        self, version: ClassificationModelVersion, artifacts_dir: Path
    ) -> ClassifierRuntime: ...


def artifact_dir(artifacts_dir: Path, version: str) -> Path:
    return artifacts_dir / CAPABILITY_DIR / version


def load_verified(
    artifacts_dir: Path, name: str, version: str, expected_manifest_sha256: str | None
) -> ClassifierRuntime:
    """Load an artifact and prove it is the one that was registered."""
    directory = artifact_dir(artifacts_dir, version)
    model_json = directory / "model.json"
    if not model_json.is_file():
        raise ModelUnavailableError("The model artifacts are not installed on this server")
    if expected_manifest_sha256 is None or sha256_file(model_json) != expected_manifest_sha256:
        raise ModelUnavailableError("The model artifacts do not match the registered version")
    runtime = ClassifierRuntime.load(directory, artifacts_dir / BACKBONE_DIR)
    if runtime.manifest.get("name") != name or runtime.manifest.get("version") != version:
        raise ModelUnavailableError("The model artifacts do not match the registered version")
    return runtime


class CachedRuntimeProvider:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._key: tuple[object, str | None] | None = None
        self._runtime: ClassifierRuntime | None = None

    def runtime_for(
        self, version: ClassificationModelVersion, artifacts_dir: Path
    ) -> ClassifierRuntime:
        key = (version.id, version.artifact_manifest_sha256)
        with self._lock:
            if self._runtime is None or self._key != key:
                self._runtime = load_verified(
                    artifacts_dir, version.name, version.version, version.artifact_manifest_sha256
                )
                self._key = key
            return self._runtime


_PROVIDER = CachedRuntimeProvider()


def get_runtime_provider() -> RuntimeProvider:
    """FastAPI dependency (tests override it to inject a fake runtime)."""
    return _PROVIDER
