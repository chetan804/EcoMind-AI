#!/usr/bin/env python3
"""TACO licence audit and owner-run image import (commercial-use policy).

TACO (https://github.com/pedropro/TACO) lists a per-image ``license`` string in
``data/annotations.json``. Production models may only use images whose licence is KNOWN to allow
commercial use: CC BY, CC BY-SA, CC0 or public domain (attribution and share-alike duties are recorded,
not dropped). Everything else is excluded:

  allowed              CC BY / CC BY-SA (any version), CC0, public domain
  noncommercial        a licence containing NC
  noderivatives        a licence containing ND
  odbl                 "ODBL (c) OpenLitterMap & Contributors": a database licence with share-alike duties
                       whose effect on a trained model needs a legal opinion. Excluded unless
                       --allow-odbl is given on purpose.
  unspecified_cc       just "CC": the variant (BY, NC, ND, SA) is not stated, so commercial use cannot be shown
  unknown              empty or unrecognised

Two subcommands (stdlib only, no network except where stated):

  audit   Read annotations.json (a path, or --download to fetch it from codeload.github.com) and write
            docs/ml/dataset-research/taco-licence-audit.json (counts, no image URLs) and, for the
            owner, datasets/external/taco/eligible_images.csv (git-ignored).
          An owner who checked an image's licence AT ITS SOURCE (for example the original Flickr page)
          can record that in datasets/external/taco/verification.csv
          (image_id,licence,evidence_url,verified_on,verified_by). A verified licence replaces the
          annotation value only if the evidence URL and date are filled in.
  import  Download the eligible images (OWNER-RUN: needs network access to the image hosts, which the
          build sandbox does not have) into datasets/external/taco/images/ with SHA-256 and licence
          provenance in import_manifest.json, plus a COCO subset restricted to those images.

    python scripts/ml/taco_licence.py audit --download
    python scripts/ml/taco_licence.py import --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TACO_ZIP = "https://codeload.github.com/pedropro/TACO/zip/refs/heads/master"
EXTERNAL = ROOT / "datasets" / "external" / "taco"
REPORT = ROOT / "docs" / "ml" / "dataset-research" / "taco-licence-audit.json"
MAX_IMAGE_BYTES = 25 * 1024 * 1024
ALLOWED, EXCLUDED_CATEGORIES = (
    "allowed",
    (
        "noncommercial",
        "noderivatives",
        "odbl",
        "unspecified_cc",
        "unknown",
    ),
)

_CC_BY = re.compile(r"^CC[ _-]?BY(?:[ _-]?SA)?(?:[ _-]?\d(?:\.\d)?)?$", re.IGNORECASE)
_CC0 = re.compile(
    r"^(?:CC0(?:[ _-]?1\.0)?|CC[ _-]?ZERO|PDM(?:[ _-]?1\.0)?|PUBLIC[ _-]?DOMAIN)$", re.IGNORECASE
)
_NC = re.compile(r"(?:^|[^A-Z])NC(?:[^A-Z]|$)", re.IGNORECASE)
_ND = re.compile(r"(?:^|[^A-Z])ND(?:[^A-Z]|$)", re.IGNORECASE)
_NC_LICENSE_NAME = re.compile(r"NON[ -]?COMMERCIAL", re.IGNORECASE)


class UsageError(ValueError):
    """The input cannot be used (reported without a traceback)."""


def classify(licence: str | None) -> str:
    """Category of one licence string (see the module docstring)."""
    text = (licence or "").strip()
    if not text:
        return "unknown"
    upper = text.upper()
    if "ODBL" in upper or "ODC-ODBL" in upper:
        return "odbl"
    if _NC.search(text) or _NC_LICENSE_NAME.search(text):
        return "noncommercial"
    if _ND.search(text) or "NO DERIV" in upper:
        return "noderivatives"
    if _CC0.match(text) or _CC_BY.match(text):
        return ALLOWED
    if re.fullmatch(r"CC", text, re.IGNORECASE):
        return "unspecified_cc"
    return "unknown"


@dataclass(frozen=True)
class Verification:
    licence: str
    evidence_url: str
    verified_on: str
    verified_by: str


def load_verifications(path: Path) -> dict[int, Verification]:
    """Owner-recorded source checks. Rows without evidence URL and date are ignored on purpose."""
    if not path.exists():
        return {}
    found: dict[int, Verification] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                image_id = int(row["image_id"])
            except (KeyError, TypeError, ValueError):
                continue
            item = Verification(
                licence=(row.get("licence") or "").strip(),
                evidence_url=(row.get("evidence_url") or "").strip(),
                verified_on=(row.get("verified_on") or "").strip(),
                verified_by=(row.get("verified_by") or "").strip(),
            )
            if item.licence and item.evidence_url.startswith("https://") and item.verified_on:
                found[image_id] = item
    return found


@dataclass(frozen=True)
class Decision:
    image_id: int
    file_name: str
    source_licence: str | None
    licence: str | None
    category: str
    basis: str  # "annotations" or "owner_verification"
    eligible: bool
    url: str


def audit_images(
    data: Mapping[str, Any],
    *,
    verifications: Mapping[int, Verification] | None = None,
    allow_odbl: bool = False,
) -> list[Decision]:
    verified = verifications or {}
    decisions: list[Decision] = []
    for image in data.get("images", []):
        image_id = int(image["id"])
        source = image.get("license")
        override = verified.get(image_id)
        licence, basis = (override.licence, "owner_verification") if override else (source, "annotations")
        category = classify(licence)
        eligible = category == ALLOWED or (allow_odbl and category == "odbl")
        url = str(image.get("flickr_url") or image.get("flickr_640_url") or "")
        decisions.append(
            Decision(
                image_id, str(image.get("file_name", "")), source, licence, category, basis, eligible, url
            )
        )
    return decisions


def summarise(
    data: Mapping[str, Any], decisions: Iterable[Decision], *, allow_odbl: bool, input_sha256: str
) -> dict[str, Any]:
    decisions = list(decisions)
    objects: Counter[int] = Counter(int(a["image_id"]) for a in data.get("annotations", []))
    by_category = Counter(d.category for d in decisions)
    objects_by_category: Counter[str] = Counter()
    for d in decisions:
        objects_by_category[d.category] += objects[d.image_id]
    eligible = [d for d in decisions if d.eligible]
    return {
        "dataset": "TACO (official annotations.json)",
        "input_sha256": input_sha256,
        "policy": (
            "Eligible only if the licence is CC BY, CC BY-SA, CC0 or public domain, from the annotation "
            "file or from an owner-recorded check at the image source. NC, ND, ODbL (unless --allow-odbl), "
            "bare 'CC', empty and unknown are excluded."
        ),
        "allow_odbl": allow_odbl,
        "images_total": len(decisions),
        "annotations_total": len(data.get("annotations", [])),
        "images_by_category": dict(sorted(by_category.items())),
        "objects_by_category": dict(sorted(objects_by_category.items())),
        "source_licence_strings": dict(Counter(str(d.source_licence) for d in decisions).most_common()),
        "owner_verified_images": sum(1 for d in decisions if d.basis == "owner_verification"),
        "eligible_images": len(eligible),
        "eligible_objects": sum(objects[d.image_id] for d in eligible),
        "attribution_required_for_eligible": sum(1 for d in eligible if d.category == ALLOWED),
    }


def write_eligible_csv(decisions: Iterable[Decision], path: Path) -> int:
    rows = [d for d in decisions if d.eligible]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["image_id", "file_name", "licence", "basis", "url"])
        for d in rows:
            writer.writerow([d.image_id, d.file_name, d.licence, d.basis, d.url])
    return len(rows)


def load_annotations(path: Path | None, download: bool) -> tuple[dict[str, Any], str]:
    if download:
        print(f"Downloading {TACO_ZIP}")
        with urllib.request.urlopen(TACO_ZIP, timeout=180) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
        name = next((n for n in archive.namelist() if n.endswith("/data/annotations.json")), None)
        if name is None:
            raise UsageError("annotations.json not found in the downloaded archive")
        raw = archive.read(name)
    elif path is not None and path.exists():
        raw = path.read_bytes()
    else:
        raise UsageError("give --annotations PATH or --download")
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise UsageError("annotations file is not valid JSON") from error
    if not isinstance(data, dict) or "images" not in data:
        raise UsageError("annotations file has no 'images' list (is it the COCO file?)")
    return data, hashlib.sha256(raw).hexdigest()


def run_audit(args: argparse.Namespace) -> int:
    data, digest = load_annotations(Path(args.annotations) if args.annotations else None, args.download)
    verifications = load_verifications(Path(args.verification))
    decisions = audit_images(data, verifications=verifications, allow_odbl=args.allow_odbl)
    summary = summarise(data, decisions, allow_odbl=args.allow_odbl, input_sha256=digest)
    summary["audited_on"] = datetime.now(UTC).date().isoformat()
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    count = write_eligible_csv(decisions, Path(args.eligible))
    print(
        json.dumps(
            {k: summary[k] for k in ("images_total", "images_by_category", "eligible_images")}, indent=2
        )
    )
    print(f"Report: {args.report}\nEligible list ({count} images): {args.eligible}")
    if count == 0:
        print(
            "No image is eligible: nothing may be imported. See docs/ml/dataset-research/TACO_LICENCE_AUDIT.md."
        )
    return 0


# --- import (owner-run) ------------------------------------------------------------------------------

Fetch = Callable[[str], bytes]


def http_fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("only https image URLs are fetched")
    request = urllib.request.Request(
        url, headers={"User-Agent": "EcoMind-AI dataset audit (contact: project owner)"}
    )  # noqa: S310
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        body = bytes(response.read(MAX_IMAGE_BYTES + 1))
    if len(body) > MAX_IMAGE_BYTES:
        raise ValueError("image larger than the 25 MB limit")
    return body


def looks_like_image(body: bytes) -> bool:
    return body.startswith(b"\xff\xd8\xff") or body.startswith(b"\x89PNG\r\n\x1a\n")


def safe_relative(file_name: str) -> Path:
    path = Path(file_name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe file name {file_name!r}")
    return path


def import_images(
    rows: list[dict[str, str]], dest: Path, fetch: Fetch, *, pause: float = 0.0
) -> dict[str, Any]:
    """Download each eligible image (resumable); every file is checked and hashed."""
    imported: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for row in rows:
        try:
            target = dest / safe_relative(row["file_name"])
            if target.exists():
                body = target.read_bytes()
            else:
                body = fetch(row["url"])
                if not looks_like_image(body):
                    raise ValueError("not a JPEG/PNG file")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
                if pause:
                    time.sleep(pause)
        except (OSError, ValueError) as error:
            failed.append(
                {"image_id": row["image_id"], "reason": type(error).__name__ + ": " + str(error)[:120]}
            )
            continue
        imported.append(
            {
                "image_id": int(row["image_id"]),
                "file_name": row["file_name"],
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
                "licence": row["licence"],
                "licence_basis": row["basis"],
                "source_url": row["url"],
            }
        )
    return {"imported": imported, "failed": failed}


def coco_subset(data: Mapping[str, Any], image_ids: set[int]) -> dict[str, Any]:
    return {
        "info": data.get("info"),
        "licenses": data.get("licenses", []),
        "categories": data.get("categories", []),
        "images": [i for i in data["images"] if int(i["id"]) in image_ids],
        "annotations": [a for a in data["annotations"] if int(a["image_id"]) in image_ids],
    }


def run_import(args: argparse.Namespace, fetch: Fetch = http_fetch) -> int:
    eligible_path = Path(args.eligible)
    if not eligible_path.exists():
        raise UsageError(f"{eligible_path} not found: run the audit first")
    with eligible_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        print(
            "The eligible list is empty: nothing to import. Images with unknown or restricted licences are never downloaded."
        )
        return 0
    if args.limit:
        rows = rows[: args.limit]
    if args.dry_run:
        print(f"Would download {len(rows)} images into {args.dest} (no request made).")
        return 0
    result = import_images(rows, Path(args.dest), fetch, pause=args.pause)
    data, digest = load_annotations(Path(args.annotations) if args.annotations else None, args.download)
    ids = {int(r["image_id"]) for r in result["imported"]}
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "annotations_eligible.json").write_text(json.dumps(coco_subset(data, ids)), encoding="utf-8")
    manifest = {"annotations_sha256": digest, "imported_on": datetime.now(UTC).isoformat(), **result}
    (dest / "import_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"Imported {len(result['imported'])}, failed {len(result['failed'])}. Manifest: {dest / 'import_manifest.json'}"
    )
    return 0 if not result["failed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="classify every image licence")
    audit.add_argument("--annotations", help="path to TACO data/annotations.json")
    audit.add_argument(
        "--download", action="store_true", help="fetch annotations.json from codeload.github.com"
    )
    audit.add_argument("--verification", default=str(EXTERNAL / "verification.csv"))
    audit.add_argument("--report", default=str(REPORT))
    audit.add_argument("--eligible", default=str(EXTERNAL / "eligible_images.csv"))
    audit.add_argument(
        "--allow-odbl", action="store_true", help="also accept ODbL images (needs a legal opinion first)"
    )
    audit.set_defaults(handler=run_audit)
    fetch = sub.add_parser("import", help="download the eligible images (owner-run)")
    fetch.add_argument("--annotations", help="path to TACO data/annotations.json")
    fetch.add_argument("--download", action="store_true")
    fetch.add_argument("--eligible", default=str(EXTERNAL / "eligible_images.csv"))
    fetch.add_argument("--dest", default=str(EXTERNAL / "images_root"))
    fetch.add_argument("--limit", type=int, default=0)
    fetch.add_argument("--pause", type=float, default=0.2, help="seconds between downloads")
    fetch.add_argument("--dry-run", action="store_true")
    fetch.set_defaults(handler=run_import)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except UsageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
