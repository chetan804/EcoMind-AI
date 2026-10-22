"""Pre-training inspection of a *candidate* image dataset (nothing is trained here).

Run it on a downloaded dataset (a directory or the original ``.zip``) before filling in a manifest.
It reads every file once and reports, from the bytes only:

* structure and file types, class labels recovered from folder and file names (never guessed: a
  file whose label cannot be recovered, or whose folder and file name disagree, is a problem);
* readability (Pillow decodes the pixels), image sizes, and whether EXIF GPS data is present
  (a privacy finding: the files must not be redistributed or committed with that metadata);
* exact duplicates inside the dataset, byte-identical overlap with RealWaste and with the prohibited
  TrashNet/TrashBox hash list, and near-duplicates by a perceptual hash (inside the dataset, and
  against RealWaste when ``--realwaste-root`` is given);
* optionally, a comparison with the publisher's per-file SHA-256 list (Mendeley public-API JSON).

``validation_passed`` is True only when no *problem* is listed. A dataset that has not passed is not
used for training. The report contains hashes and counts only, never image data.

    python -m ml.waste_classification.data.inspect_candidate --root "<dir or zip>" \
        --source-json mendeley-h5pxbsdz4m.json --realwaste-root <RealWaste folder>
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import numpy as np
from PIL import ExifTags, Image, UnidentifiedImageError

from ml.waste_classification.data.imagefolder import IMAGE_SUFFIXES
from ml.waste_classification.data.provenance import REPO, load_denylist

# Class words accepted in folder and file names -> EcoMind class. Deliberately explicit: a word that
# is not here (for example "trash", "organic") is reported as unmapped and never given a material.
CLASS_WORDS: dict[str, str] = {
    "cardboard": "cardboard",
    "glass": "glass",
    "metal": "metal",
    "paper": "paper",
    "plastic": "plastic",
}
# "<site>_<Class> (<n>).jpg": the pattern of the Mendeley release, e.g. "UHW_Plastic (95).jpg".
FILENAME = re.compile(r"^(?P<site>[A-Za-z0-9]+)_(?P<word>[A-Za-z]+)\s*\((?P<n>\d+)\)\.\w+$")
MIN_IMAGES_PER_CLASS = 30
DHASH_MAX_DISTANCE = 4  # bits out of 64: images this close are treated as near-duplicates
_GPS_IFD = 0x8825

Source = Iterator[tuple[str, Callable[[], bytes]]]


def iter_source(root: Path) -> Source:
    """``(relative path, reader)`` for every file under a directory or inside a zip, sorted."""
    if root.is_file() and root.suffix.lower() == ".zip":
        archive = zipfile.ZipFile(root)
        for info in sorted(archive.infolist(), key=lambda i: i.filename):
            if not info.is_dir():
                yield info.filename, (lambda name=info.filename: archive.read(name))  # type: ignore[misc]
        return
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        yield path.relative_to(root).as_posix(), path.read_bytes


def dhash(image: Image.Image) -> int:
    """64-bit difference hash: robust to re-encoding and small resizes, not to crops."""
    small = image.convert("L").resize((9, 8), Image.Resampling.BILINEAR)
    pixels = np.asarray(small, dtype=np.int16)
    bits = 0
    for flag in (pixels[:, :-1] > pixels[:, 1:]).ravel():
        bits = (bits << 1) | int(flag)
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def labels_from_path(relpath: str) -> dict[str, Any]:
    """Recover the class from the file name and from the folders; report any disagreement."""
    parts = relpath.split("/")
    name = parts[-1]
    match = FILENAME.match(name)
    site = match["site"] if match else None
    from_name = CLASS_WORDS.get(match["word"].lower()) if match else None
    folder_classes = {
        CLASS_WORDS[word]
        for folder in parts[:-1]
        for word in CLASS_WORDS
        if word in re.sub(r"[^a-z]", " ", folder.lower()).split()
    }
    return {
        "site": site,
        "from_filename": from_name,
        "from_folders": sorted(folder_classes),
        "label": from_name
        if from_name and folder_classes <= {from_name}
        else (next(iter(folder_classes)) if not from_name and len(folder_classes) == 1 else None),
        "conflict": bool(from_name and folder_classes and folder_classes != {from_name})
        or len(folder_classes) > 1,
    }


def _has_gps(image: Image.Image) -> bool:
    try:
        exif = image.getexif()
        return bool(exif.get_ifd(ExifTags.IFD.GPSInfo)) or _GPS_IFD in exif
    except (AttributeError, KeyError, ValueError, OSError):
        return False


def inspect_file(relpath: str, data: bytes) -> dict[str, Any]:
    row: dict[str, Any] = {
        "file": relpath,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "is_image_file": Path(relpath).suffix.lower() in IMAGE_SUFFIXES,
        **labels_from_path(relpath),
    }
    if not row["is_image_file"]:
        return row
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()  # decodes every pixel: catches truncated files that verify() would miss
            row.update(
                readable=True,
                width=image.width,
                height=image.height,
                mode=image.mode,
                has_gps=_has_gps(image),
                dhash=dhash(image),
            )
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ) as error:
        row.update(readable=False, error=type(error).__name__)
    return row


def near_duplicate_pairs(
    rows: list[dict[str, Any]], *, within: bool = True
) -> list[tuple[str, str]]:
    """Pairs of readable, byte-different images whose perceptual hashes are within the threshold."""
    items = [r for r in rows if r.get("dhash") is not None]
    pairs: list[tuple[str, str]] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if a["sha256"] != b["sha256"] and hamming(a["dhash"], b["dhash"]) <= DHASH_MAX_DISTANCE:
                pairs.append((a["file"], b["file"]))
    return pairs


def cross_near_duplicates(
    rows: list[dict[str, Any]], other: Mapping[str, int]
) -> list[tuple[str, str]]:
    """Candidate images that are near-identical to one of ``other`` (name -> dhash)."""
    found: list[tuple[str, str]] = []
    for r in rows:
        if r.get("dhash") is None:
            continue
        for name, value in other.items():
            if hamming(r["dhash"], value) <= DHASH_MAX_DISTANCE:
                found.append((r["file"], name))
                break
    return found


def realwaste_hashes(table: Path) -> dict[str, str]:
    """sha256 -> file, from the committed per-file table (no image download needed)."""
    lines = table.read_text().splitlines()
    header = lines[0].split("\t")
    out: dict[str, str] = {}
    for line in lines[1:]:
        cells = dict(zip(header, line.split("\t"), strict=True))
        out[cells["sha256"]] = cells["file"]
    return out


def realwaste_dhashes(root: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for path in sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES):
        with Image.open(path) as image:
            out[path.relative_to(root).as_posix()] = dhash(image)
    return out


def compare_with_publisher(rows: list[dict[str, Any]], api: Mapping[str, Any]) -> dict[str, Any]:
    """Compare against the publisher's per-file list (Mendeley public-API JSON, key ``files``)."""
    listed = {
        f["filename"]: (
            f["content_details"]["sha256_hash"].lower(),
            int(f["content_details"]["size"]),
        )
        for f in api.get("files", [])
    }
    mine = {Path(r["file"]).name: (r["sha256"], r["size"]) for r in rows if r["is_image_file"]}
    return {
        "listed": len(listed),
        "found": len(mine),
        "missing_from_download": sorted(set(listed) - set(mine)),
        "not_in_publisher_list": sorted(set(mine) - set(listed)),
        "hash_or_size_mismatch": sorted(n for n in set(listed) & set(mine) if listed[n] != mine[n]),
        "licence": (api.get("data_licence") or {}).get("short_name"),
        "version": api.get("version"),
        "doi": (api.get("doi") or {}).get("id"),
    }


def inspect_dataset(
    source: Source,
    *,
    denylist: frozenset[str],
    realwaste_sha: Mapping[str, str] | None = None,
    realwaste_hash_of_images: Mapping[str, int] | None = None,
    publisher: Mapping[str, Any] | None = None,
    expected_images: int | None = None,
) -> dict[str, Any]:
    rows = [inspect_file(name, read()) for name, read in source]
    images = [r for r in rows if r["is_image_file"]]
    ignored = sorted(r["file"] for r in rows if not r["is_image_file"])
    unreadable = sorted(r["file"] for r in images if not r.get("readable"))
    unmapped = sorted(r["file"] for r in images if r["label"] is None and not r["conflict"])
    conflicts = sorted(r["file"] for r in images if r["conflict"])
    classes = Counter(r["label"] for r in images if r["label"])
    by_site: dict[str, Counter[str]] = defaultdict(Counter)
    for r in images:
        if r["label"]:
            by_site[r["site"] or "unknown"][r["label"]] += 1
    digests = Counter(r["sha256"] for r in images)
    duplicate_groups = sorted(
        sorted(r["file"] for r in images if r["sha256"] == d) for d, n in digests.items() if n > 1
    )
    prohibited = sorted(r["file"] for r in images if r["sha256"] in denylist)
    overlap = sorted(r["file"] for r in images if realwaste_sha and r["sha256"] in realwaste_sha)
    near = near_duplicate_pairs([r for r in images if r.get("readable")])
    cross_near = (
        cross_near_duplicates([r for r in images if r.get("readable")], realwaste_hash_of_images)
        if realwaste_hash_of_images
        else None
    )
    report: dict[str, Any] = {
        "files_total": len(rows),
        "image_files": len(images),
        "ignored_non_image_files": ignored,
        "readable": sum(1 for r in images if r.get("readable")),
        "unreadable": unreadable,
        "class_counts": dict(sorted(classes.items())),
        "class_counts_by_site": {s: dict(sorted(c.items())) for s, c in sorted(by_site.items())},
        "unmapped_files": unmapped,
        "label_conflicts": conflicts,
        "image_size_range": {
            "min_side": min(
                (min(r["width"], r["height"]) for r in images if r.get("readable")), default=None
            ),
            "max_side": max(
                (max(r["width"], r["height"]) for r in images if r.get("readable")), default=None
            ),
        },
        "files_with_exif_gps": sorted(r["file"] for r in images if r.get("has_gps")),
        "exact_duplicate_groups": duplicate_groups,
        "byte_identical_to_prohibited_hashes": prohibited,
        "byte_identical_to_realwaste": overlap if realwaste_sha is not None else "not checked",
        "near_duplicate_pairs_within": len(near),
        "near_duplicate_pairs_with_realwaste": (
            len(cross_near) if cross_near is not None else "not checked"
        ),
        "publisher_comparison": compare_with_publisher(rows, publisher)
        if publisher
        else "not checked",
        "file_table": [
            {k: r[k] for k in ("file", "sha256", "size", "label", "site") if k in r} for r in rows
        ],
    }
    problems: list[str] = []
    if not images:
        problems.append("no image files found")
    if unreadable:
        problems.append(f"{len(unreadable)} image file(s) cannot be decoded")
    if unmapped:
        problems.append(f"{len(unmapped)} image file(s) have no recoverable class")
    if conflicts:
        problems.append(
            f"{len(conflicts)} image file(s) have a folder and a file name that disagree"
        )
    if prohibited:
        problems.append(
            f"{len(prohibited)} file(s) are byte-identical to prohibited TrashNet/TrashBox images"
        )
    if overlap:
        problems.append(
            f"{len(overlap)} file(s) are byte-identical to RealWaste images (exclude them)"
        )
    if realwaste_sha is None:
        problems.append("overlap with RealWaste was not checked (pass --realwaste-table)")
    if expected_images is not None and len(images) != expected_images:
        problems.append(f"{len(images)} images found, the publisher states {expected_images}")
    for name in CLASS_WORDS.values():
        if classes.get(name, 0) < MIN_IMAGES_PER_CLASS:
            problems.append(
                f"class {name!r} has {classes.get(name, 0)} images (< {MIN_IMAGES_PER_CLASS})"
            )
    if publisher:
        cmp = report["publisher_comparison"]
        for key in ("missing_from_download", "not_in_publisher_list", "hash_or_size_mismatch"):
            if cmp[key]:
                problems.append(
                    f"publisher comparison: {len(cmp[key])} file(s) {key.replace('_', ' ')}"
                )
    else:
        problems.append(
            "files were not compared with the publisher's per-file hashes (pass --source-json)"
        )
    report["problems"] = problems
    report["validation_passed"] = not problems
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, required=True, help="downloaded directory or .zip")
    parser.add_argument(
        "--source-json", type=Path, help="publisher per-file list (Mendeley public-API JSON)"
    )
    parser.add_argument(
        "--realwaste-table",
        type=Path,
        default=REPO / "datasets" / "manifests" / "realwaste-2.0.files.tsv",
    )
    parser.add_argument(
        "--realwaste-root", type=Path, help="RealWaste images, for the near-duplicate check"
    )
    parser.add_argument("--expected-images", type=int)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = inspect_dataset(
        iter_source(args.root),
        denylist=load_denylist(),
        realwaste_sha=realwaste_hashes(args.realwaste_table),
        realwaste_hash_of_images=realwaste_dhashes(args.realwaste_root)
        if args.realwaste_root
        else None,
        publisher=json.loads(args.source_json.read_text()) if args.source_json else None,
        expected_images=args.expected_images,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"images={report['image_files']} classes={report['class_counts']} "
        f"passed={report['validation_passed']}"
    )
    for problem in report["problems"]:
        print(f"  PROBLEM: {problem}")
    return 0 if report["validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
