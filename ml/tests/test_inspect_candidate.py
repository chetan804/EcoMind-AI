"""Pre-training inspection of a candidate dataset: every failure mode is reported."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from ml.waste_classification.data import inspect_candidate as ic

CLASSES = ["Cardboard", "Glass", "Metal", "Paper", "Plastic"]


def jpeg(seed: int, *, size: int = 64, gps: bool = False) -> bytes:
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, (size, size, 3), dtype=np.uint8)
    image = Image.fromarray(pixels)
    buffer = io.BytesIO()
    if gps:
        exif = Image.Exif()
        exif.get_ifd(0x8825)[1] = "N"  # GPSLatitudeRef: any GPS tag marks the file
        image.save(buffer, "JPEG", exif=exif)
    else:
        image.save(buffer, "JPEG")
    return buffer.getvalue()


def tree(per_class: int = 31) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    seed = 0
    for cls in CLASSES:
        for n in range(1, per_class + 1):
            seed += 1
            files[f"Recyclable Waste Image Dataset/{cls}/UHW_{cls} ({n}).jpg"] = jpeg(seed)
    return files


def source(files: dict[str, bytes]) -> ic.Source:
    return iter((name, (lambda data=data: data)) for name, data in sorted(files.items()))


def publisher(files: dict[str, bytes], **tamper: Any) -> dict[str, Any]:
    listed = [
        {
            "filename": Path(name).name,
            "content_details": {"sha256_hash": hashlib.sha256(data).hexdigest(), "size": len(data)},
        }
        for name, data in files.items()
    ]
    return {
        "files": listed,
        "version": 1,
        "doi": {"id": "10.17632/x.1"},
        "data_licence": {"short_name": "CC BY 4.0"},
        **tamper,
    }


def run(files: dict[str, bytes], **kwargs: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "denylist": frozenset({"0" * 64}),
        "realwaste_sha": {},
        "publisher": publisher(files),
    }
    return ic.inspect_dataset(source(files), **{**defaults, **kwargs})


def test_a_clean_dataset_passes_and_reports_class_counts() -> None:
    report = run(tree(), expected_images=155)
    assert report["problems"] == [] and report["validation_passed"] is True
    assert report["class_counts"] == {c.lower(): 31 for c in CLASSES}
    assert report["class_counts_by_site"] == {"UHW": {c.lower(): 31 for c in CLASSES}}
    assert report["readable"] == 155 and report["files_with_exif_gps"] == []


def test_an_unreadable_file_fails_validation() -> None:
    files = tree()
    first = next(iter(files))
    files[first] = files[first][:200]  # truncated JPEG
    report = run(files, publisher=publisher(files))
    assert report["unreadable"] == [first] and not report["validation_passed"]


def test_unmapped_labels_are_never_given_a_material() -> None:
    files = tree()
    files["Recyclable Waste Image Dataset/Misc/UHW_Trash (1).jpg"] = jpeg(9001)
    files["Recyclable Waste Image Dataset/Misc/photo.jpg"] = jpeg(9002)
    report = run(files, publisher=publisher(files))
    assert len(report["unmapped_files"]) == 2
    assert "trash" not in report["class_counts"] and not report["validation_passed"]


def test_folder_and_file_name_that_disagree_are_a_conflict() -> None:
    files = tree()
    files["Recyclable Waste Image Dataset/Glass/UHW_Plastic (900).jpg"] = jpeg(9003)
    report = run(files, publisher=publisher(files))
    assert report["label_conflicts"] == [
        "Recyclable Waste Image Dataset/Glass/UHW_Plastic (900).jpg"
    ]
    assert not report["validation_passed"]


def test_a_label_can_come_from_the_folder_when_the_file_name_has_no_class() -> None:
    row = ic.labels_from_path("data/Metal cans/IMG_0001.jpg")
    assert row["label"] == "metal" and not row["conflict"]
    assert ic.labels_from_path("data/Mixed/IMG_0001.jpg")["label"] is None


def test_files_identical_to_a_prohibited_image_are_reported() -> None:
    files = tree()
    victim = next(iter(files))
    digest = hashlib.sha256(files[victim]).hexdigest()
    report = run(files, denylist=frozenset({digest}), publisher=publisher(files))
    assert report["byte_identical_to_prohibited_hashes"] == [victim]
    assert any("prohibited" in p for p in report["problems"])


def test_overlap_with_realwaste_is_exact_and_fails_validation() -> None:
    files = tree()
    victim = next(iter(files))
    digest = hashlib.sha256(files[victim]).hexdigest()
    report = run(files, realwaste_sha={digest: "Glass/Glass_1.jpg"}, publisher=publisher(files))
    assert report["byte_identical_to_realwaste"] == [victim] and not report["validation_passed"]


def test_skipping_the_realwaste_check_is_itself_a_problem() -> None:
    report = run(tree(), realwaste_sha=None)
    assert report["byte_identical_to_realwaste"] == "not checked"
    assert not report["validation_passed"]


def test_exact_duplicates_and_near_duplicates_are_found() -> None:
    files = tree()
    names = sorted(files)
    files[names[0].replace("(1).jpg", "(500).jpg")] = files[names[0]]  # byte copy
    pixels = np.asarray(Image.open(io.BytesIO(files[names[40]])).convert("RGB")).copy()
    pixels[0, 0] = 255 - pixels[0, 0]  # one pixel changed: not byte-identical, same picture
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, "JPEG")
    files[names[40].replace(".jpg", "x.jpg").replace("(", "(7")] = buffer.getvalue()
    report = run(files, publisher=publisher(files))
    assert len(report["exact_duplicate_groups"]) == 1
    assert report["near_duplicate_pairs_within"] >= 1


def test_gps_metadata_is_reported_as_a_privacy_finding() -> None:
    files = tree()
    files["Recyclable Waste Image Dataset/Metal/UHW_Metal (700).jpg"] = jpeg(777, gps=True)
    report = run(files, publisher=publisher(files))
    assert report["files_with_exif_gps"] == [
        "Recyclable Waste Image Dataset/Metal/UHW_Metal (700).jpg"
    ]


def test_a_class_with_too_few_images_fails() -> None:
    report = run(tree(per_class=5), publisher=publisher(tree(per_class=5)))
    assert any("(< 30)" in p for p in report["problems"]) and not report["validation_passed"]


def test_the_publisher_list_catches_a_modified_missing_or_extra_file() -> None:
    files = tree()
    pub = publisher(files)
    modified = dict(files)
    victim = next(iter(modified))
    modified[victim] = jpeg(123456)
    modified["Recyclable Waste Image Dataset/Paper/UHW_Paper (9999).jpg"] = jpeg(123457)
    del modified[sorted(modified)[-2]]
    report = run(modified, publisher=pub)
    cmp = report["publisher_comparison"]
    assert Path(victim).name in cmp["hash_or_size_mismatch"]
    assert cmp["not_in_publisher_list"] and cmp["missing_from_download"]
    assert not report["validation_passed"]


def test_the_wrong_image_count_fails() -> None:
    assert not run(tree(), expected_images=1000)["validation_passed"]


def test_a_zip_and_a_directory_give_the_same_report(tmp_path: Path) -> None:
    files = tree(per_class=3)
    archive = tmp_path / "d.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    folder = tmp_path / "dir"
    for name, data in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    kwargs: dict[str, Any] = {"denylist": frozenset({"0" * 64}), "realwaste_sha": {}}
    a = ic.inspect_dataset(ic.iter_source(archive), **kwargs)
    b = ic.inspect_dataset(ic.iter_source(folder), **kwargs)
    assert a["file_table"] == b["file_table"] and a["class_counts"] == b["class_counts"]


def test_the_report_holds_hashes_and_counts_only() -> None:
    report = run(tree(per_class=2), publisher=publisher(tree(per_class=2)))
    assert set(report["file_table"][0]) <= {"file", "sha256", "size", "label", "site"}


@pytest.mark.parametrize("name", ["UHW_Plastic (95).jpg", "CWMF_Cardboard  (10).jpg"])
def test_the_published_file_name_pattern_is_parsed(name: str) -> None:
    row = ic.labels_from_path(f"x/{name}")
    assert row["label"] in {"plastic", "cardboard"} and row["site"] in {"UHW", "CWMF"}
