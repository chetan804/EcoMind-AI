"""TACO licence audit and owner-run import (no network). The Flickr evidence tool is in test_taco_evidence.py."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "ml"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


audit = load("taco_licence")

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32


@pytest.mark.parametrize(
    ("licence", "category"),
    [
        ("CC BY 2.0", "allowed"),
        ("CC BY-SA 4.0", "allowed"),
        ("cc-by-2.0", "allowed"),
        ("CC0 1.0", "allowed"),
        ("PDM 1.0", "allowed"),
        ("Public Domain", "allowed"),
        ("CC BY-NC 2.0", "noncommercial"),
        ("CC BY-NC-SA 4.0", "noncommercial"),
        ("Attribution-NonCommercial License", "noncommercial"),
        ("CC BY-ND 2.0", "noderivatives"),
        ("CC BY-NC-ND 2.0", "noncommercial"),
        ("ODBL (c) OpenLitterMap & Contributors", "odbl"),
        ("CC", "unspecified_cc"),
        ("", "unknown"),
        (None, "unknown"),
        ("All Rights Reserved", "unknown"),
        ("No known copyright restrictions", "unknown"),
        ("unmapped Flickr licence id 12", "unknown"),
    ],
)
def test_classification_never_admits_an_unproven_licence(licence: str | None, category: str) -> None:
    assert audit.classify(licence) == category


def coco() -> dict[str, object]:
    def image(
        i: int, licence: str | None, url: str = "https://img.example/img/123456789.jpg"
    ) -> dict[str, object]:
        return {"id": i, "file_name": f"batch_1/{i:06d}.jpg", "license": licence, "flickr_url": url}

    return {
        "info": {},
        "licenses": [],
        "categories": [{"id": 0, "name": "Bottle"}],
        "images": [
            image(0, "CC BY 2.0"),
            image(1, "CC"),
            image(2, None),
            image(3, "CC BY-NC 2.0"),
            image(4, "ODBL (c) OpenLitterMap & Contributors"),
        ],
        "annotations": [{"id": n, "image_id": n % 5, "category_id": 0} for n in range(10)],
    }


def test_audit_counts_and_default_eligibility() -> None:
    data = coco()
    decisions = audit.audit_images(data)
    assert [d.eligible for d in decisions] == [True, False, False, False, False]
    summary = audit.summarise(data, decisions, allow_odbl=False, input_sha256="x")
    assert summary["images_by_category"] == {
        "allowed": 1,
        "noncommercial": 1,
        "odbl": 1,
        "unknown": 1,
        "unspecified_cc": 1,
    }
    assert summary["eligible_images"] == 1 and summary["eligible_objects"] == 2
    assert "url" not in json.dumps(summary)  # the report carries no image URLs
    opted_in = audit.audit_images(data, allow_odbl=True)
    assert [d.eligible for d in opted_in] == [True, False, False, False, True]


def test_owner_verification_needs_evidence_and_a_date(tmp_path: Path) -> None:
    path = tmp_path / "verification.csv"
    path.write_text(
        "image_id,licence,evidence_url,verified_on,verified_by\n"
        "1,CC BY 2.0,https://www.flickr.com/photo.gne?id=1,2026-10-21,owner\n"
        "2,CC BY 2.0,,2026-10-21,owner\n"
        "3,CC BY 2.0,http://insecure.example/x,2026-10-21,owner\n"
        "x,CC BY 2.0,https://e.example/,2026-10-21,owner\n"
        "4,CC BY-NC 2.0,https://www.flickr.com/photo.gne?id=4,2026-10-21,owner\n",
        encoding="utf-8",
    )
    found = audit.load_verifications(path)
    assert set(found) == {1, 4}
    decisions = audit.audit_images(coco(), verifications=found)
    by_id = {d.image_id: d for d in decisions}
    assert by_id[1].eligible and by_id[1].basis == "owner_verification"
    assert not by_id[2].eligible  # a row without evidence changes nothing
    assert audit.audit_images(coco(), verifications={4: found[4]})[4].eligible is False


def test_cli_audit_writes_report_and_eligible_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    annotations = tmp_path / "annotations.json"
    annotations.write_text(json.dumps(coco()), encoding="utf-8")
    code = audit.main(
        [
            "audit",
            "--annotations",
            str(annotations),
            "--verification",
            str(tmp_path / "none.csv"),
            "--report",
            str(tmp_path / "report.json"),
            "--eligible",
            str(tmp_path / "eligible.csv"),
        ]
    )
    assert code == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert (
        report["eligible_images"] == 1
        and report["input_sha256"] == hashlib.sha256(annotations.read_bytes()).hexdigest()
    )
    rows = list(csv.DictReader((tmp_path / "eligible.csv").open()))
    assert [r["image_id"] for r in rows] == ["0"]
    assert audit.main(["audit", "--annotations", str(tmp_path / "missing.json")]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("[]")
    assert audit.main(["audit", "--annotations", str(bad)]) == 2
    assert "error:" in capsys.readouterr().err


def import_args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    base = {
        "eligible": str(tmp_path / "eligible.csv"),
        "dest": str(tmp_path / "images"),
        "annotations": str(tmp_path / "annotations.json"),
        "download": False,
        "limit": 0,
        "pause": 0.0,
        "dry_run": False,
    }
    return argparse.Namespace(**{**base, **overrides})


def test_import_downloads_only_listed_images_and_records_provenance(tmp_path: Path) -> None:
    (tmp_path / "annotations.json").write_text(json.dumps(coco()), encoding="utf-8")
    (tmp_path / "eligible.csv").write_text(
        "image_id,file_name,licence,basis,url\n0,batch_1/000000.jpg,CC BY 2.0,annotations,https://img.example/img/0.jpg\n",
        encoding="utf-8",
    )
    requested: list[str] = []

    def fetch(url: str) -> bytes:
        requested.append(url)
        return JPEG

    assert audit.run_import(import_args(tmp_path), fetch=fetch) == 0
    assert requested == ["https://img.example/img/0.jpg"]
    manifest = json.loads((tmp_path / "images" / "import_manifest.json").read_text())
    assert manifest["imported"][0]["sha256"] == hashlib.sha256(JPEG).hexdigest()
    assert manifest["imported"][0]["licence"] == "CC BY 2.0"
    subset = json.loads((tmp_path / "images" / "annotations_eligible.json").read_text())
    assert [i["id"] for i in subset["images"]] == [0] and {a["image_id"] for a in subset["annotations"]} == {
        0
    }
    audit.run_import(import_args(tmp_path), fetch=fetch)
    assert len(requested) == 1  # resumable: an existing file is not downloaded again


def test_import_refuses_unsafe_names_and_non_images_and_empty_lists(tmp_path: Path) -> None:
    (tmp_path / "annotations.json").write_text(json.dumps(coco()), encoding="utf-8")
    (tmp_path / "eligible.csv").write_text(
        "image_id,file_name,licence,basis,url\n"
        "0,../escape.jpg,CC BY 2.0,annotations,https://img.example/a.jpg\n"
        "1,batch_1/000001.jpg,CC BY 2.0,annotations,https://img.example/b.jpg\n",
        encoding="utf-8",
    )
    assert audit.run_import(import_args(tmp_path), fetch=lambda _url: b"<html>") == 1
    manifest = json.loads((tmp_path / "images" / "import_manifest.json").read_text())
    assert manifest["imported"] == [] and len(manifest["failed"]) == 2
    assert not (tmp_path / "escape.jpg").exists()
    (tmp_path / "eligible.csv").write_text("image_id,file_name,licence,basis,url\n", encoding="utf-8")
    assert audit.run_import(import_args(tmp_path), fetch=lambda _url: pytest.fail("no request expected")) == 0
    with pytest.raises(audit.UsageError, match="run the audit first"):
        audit.run_import(import_args(tmp_path, eligible=str(tmp_path / "absent.csv")))


def test_import_dry_run_makes_no_request(tmp_path: Path) -> None:
    (tmp_path / "eligible.csv").write_text(
        "image_id,file_name,licence,basis,url\n0,batch_1/000000.jpg,CC BY 2.0,annotations,https://x.example/0.jpg\n",
        encoding="utf-8",
    )
    assert (
        audit.run_import(import_args(tmp_path, dry_run=True), fetch=lambda _url: pytest.fail("no request"))
        == 0
    )
    assert not (tmp_path / "images").exists()


def test_http_fetch_only_accepts_https() -> None:
    with pytest.raises(ValueError, match="https"):
        audit.http_fetch("http://example.org/a.jpg")
