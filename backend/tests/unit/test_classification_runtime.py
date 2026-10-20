from __future__ import annotations

import io
import json
import uuid
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest
from PIL import Image

from app.modules.classification.errors import InvalidImageError, ModelUnavailableError
from app.modules.classification.models import ClassificationModelVersion
from app.modules.classification.provider import (
    CachedRuntimeProvider,
    load_verified,
)
from app.modules.classification.runtime import (
    ClassifierRuntime,
    TFLiteEmbedder,
    decode_image,
    sha256_file,
)
from tests.fixtures.classification import CLASSES, MODEL_NAME, write_artifact

DIM = 12


def encoded(fmt: str, size: tuple[int, int] = (40, 30), **kwargs: object) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def test_decode_accepts_the_three_upload_formats_as_rgb() -> None:
    for fmt in ("PNG", "JPEG", "WEBP"):
        image = decode_image(encoded(fmt))
        assert image.mode == "RGB" and image.size == (40, 30)


def test_decode_rejects_unsupported_garbage_and_oversized_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(InvalidImageError):
        decode_image(encoded("BMP"))
    with pytest.raises(InvalidImageError):
        decode_image(b"definitely not an image")
    with pytest.raises(InvalidImageError):
        decode_image(b"")
    monkeypatch.setattr("app.modules.classification.runtime.MAX_PIXELS", 100)
    with pytest.raises(InvalidImageError, match="too many pixels"):
        decode_image(encoded("PNG"))


def test_decode_honours_exif_orientation() -> None:
    image = Image.new("RGB", (40, 30), (1, 2, 3))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise to display
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    assert decode_image(buffer.getvalue()).size == (30, 40)


class FakeEmbedder:
    """The mean red value selects which feature is large, so the head's answer is predictable."""

    def embed(self, images: Sequence[Image.Image]) -> npt.NDArray[np.float32]:
        rows = []
        for image in images:
            vec = np.full(DIM, 0.1, dtype=np.float32)
            vec[int(np.asarray(image)[..., 0].mean()) % 6] += 5.0
            rows.append(vec)
        return np.stack(rows)


def runtime(
    *, min_conf: float = 0.5, min_novelty: float = 0.0, temperature: float = 1.0
) -> ClassifierRuntime:
    coef = np.zeros((6, DIM), dtype=np.float32)
    for k in range(6):
        coef[k, k] = 1.0
    unit = np.full(DIM, 0.1)
    reference = np.stack([unit / np.linalg.norm(unit)]).astype(np.float32)
    manifest = {
        "name": MODEL_NAME,
        "version": "9.9.9",
        "classes": CLASSES,
        "tta_variants": ["identity", "hflip"],
        "temperature": temperature,
        "review": {"min_confidence": min_conf, "min_novelty_similarity": min_novelty},
    }
    return ClassifierRuntime(manifest, [FakeEmbedder()], coef, np.zeros(6, np.float32), reference)


def predict(rt: ClassifierRuntime, red: int):  # type: ignore[no-untyped-def]
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (red, 0, 0)).save(buffer, format="PNG")
    return rt.predict_bytes(buffer.getvalue())


def test_runtime_predicts_with_a_proper_probability_distribution() -> None:
    result = predict(runtime(), 3)
    assert result.label == "paper"
    assert sum(result.probabilities.values()) == pytest.approx(1.0)
    assert result.confidence == max(result.probabilities.values())
    assert result.inference_ms > 0


def test_temperature_changes_confidence_not_the_decision() -> None:
    sharp, soft = predict(runtime(temperature=1.0), 2), predict(runtime(temperature=5.0), 2)
    assert sharp.label == soft.label and soft.confidence < sharp.confidence


def test_review_reasons_cover_low_confidence_and_unfamiliar_images() -> None:
    assert predict(runtime(), 1).review_reasons == []
    assert predict(runtime(min_conf=0.9999), 1).review_reasons == ["low_confidence"]
    assert predict(runtime(min_novelty=1.5), 1).review_reasons == ["unfamiliar_image"]
    both = predict(runtime(min_conf=0.9999, min_novelty=1.5), 1)
    assert both.needs_review and both.review_reasons == ["low_confidence", "unfamiliar_image"]


def test_runtime_rejects_undecodable_input_before_inference() -> None:
    with pytest.raises(InvalidImageError):
        runtime().predict_bytes(b"nope")


def test_load_verifies_every_artifact_file(tmp_path: Path) -> None:
    directory = write_artifact(tmp_path, "1.0.0")
    assert ClassifierRuntime.load(directory, tmp_path).classes == CLASSES
    with (directory / "novelty_reference.npy").open("ab") as handle:
        handle.write(b"x")
    with pytest.raises(ModelUnavailableError, match=r"novelty_reference\.npy"):
        ClassifierRuntime.load(directory, tmp_path)
    (directory / "head.npz").unlink()
    with pytest.raises(ModelUnavailableError):
        ClassifierRuntime.load(directory, tmp_path)


def test_backbone_with_the_wrong_hash_is_refused(tmp_path: Path) -> None:
    fake = tmp_path / "backbone.tflite"
    fake.write_bytes(b"not a model")
    with pytest.raises(ModelUnavailableError):
        TFLiteEmbedder(fake, expected_sha256="0" * 64)
    with pytest.raises(ModelUnavailableError):
        TFLiteEmbedder(tmp_path / "missing.tflite", expected_sha256="0" * 64)


def test_load_verified_binds_the_artifact_to_the_registered_hash_name_and_version(
    tmp_path: Path,
) -> None:
    directory = write_artifact(tmp_path, "1.0.0")
    digest = sha256_file(directory / "model.json")
    assert load_verified(tmp_path, MODEL_NAME, "1.0.0", digest).manifest["version"] == "1.0.0"
    with pytest.raises(ModelUnavailableError):
        load_verified(tmp_path, MODEL_NAME, "1.0.0", "f" * 64)
    with pytest.raises(ModelUnavailableError):
        load_verified(tmp_path, MODEL_NAME, "1.0.0", None)
    with pytest.raises(ModelUnavailableError):
        load_verified(tmp_path, MODEL_NAME, "2.0.0", digest)  # no artifact for that version
    with pytest.raises(ModelUnavailableError, match="do not match"):
        load_verified(tmp_path, "other-model", "1.0.0", digest)
    manifest = json.loads((directory / "model.json").read_text())
    assert manifest["files"]


def _row(version: str, sha256: str) -> ClassificationModelVersion:
    return ClassificationModelVersion(
        id=uuid.uuid4(), name=MODEL_NAME, version=version, artifact_manifest_sha256=sha256
    )


def test_provider_loads_once_and_reloads_when_the_active_version_changes(tmp_path: Path) -> None:
    first_dir, second_dir = write_artifact(tmp_path, "1.0.0"), write_artifact(tmp_path, "1.1.0")
    one = _row("1.0.0", sha256_file(first_dir / "model.json"))
    two = _row("1.1.0", sha256_file(second_dir / "model.json"))
    provider = CachedRuntimeProvider()
    loaded = provider.runtime_for(one, tmp_path)
    assert provider.runtime_for(one, tmp_path) is loaded  # cached, not reloaded per request
    assert provider.runtime_for(two, tmp_path) is not loaded
    assert provider.runtime_for(two, tmp_path).manifest["version"] == "1.1.0"
