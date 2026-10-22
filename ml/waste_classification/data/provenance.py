"""Dataset provenance gate: no training or evaluation run starts without verified provenance.

Fails closed. A manifest that lacks a required field, names a prohibited source, carries an unknown
licence, or maps a catch-all label to a known material is *rejected*, not warned about.

* **Prohibited sources.** TrashNet and TrashBox are excluded from every new training, validation,
  test and release dataset (the owner could not obtain permission for the images TrashBox
  republishes from TrashNet). They are excluded three ways: by manifest name/URL, by a declared
  `contains_third_party_from` list, and by content: `datasets/manifests/prohibited-sha256.txt`
  holds the SHA-256 of every TrashNet image, so a byte-identical copy inside *any* other dataset is
  found and refused.
* **Licence conflicts.** When sources disagree about a licence the manifest must say so
  (`licence.status: conflicting`). A conflicting or unresolved licence allows research use only;
  `release_allowed` is False until a resolution with evidence and a date is recorded.
* **Catch-all labels.** A source label such as "Miscellaneous Trash" may not be mapped to a known
  material without an explicit written justification.
* **Leakage.** Byte-identical files must never straddle two splits, whatever their labels.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray

REPO = Path(__file__).resolve().parents[3]
DENYLIST_FILE = REPO / "datasets" / "manifests" / "prohibited-sha256.txt"

# normalised name -> reason. A name is prohibited if, lower-cased with every non-alphanumeric
# character removed, it *contains* one of these keys (so "TrashNet v2" and "trash-net" are caught).
PROHIBITED_DATASETS: dict[str, str] = {
    "trashnet": "written permission for the photographs was not obtained",
    "trashbox": "no licence; republishes TrashNet images (819 byte-identical files were found)",
}

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CATCH_ALL = re.compile(r"misc|other|rubbish|residual|trash|general", re.IGNORECASE)
_UNKNOWN_LICENCES = {"", "unknown", "none", "unlicensed", "unspecified", "tbd", "todo"}
_RELEASE_STATES = {"resolved", "verified"}


class ProvenanceError(ValueError):
    """A dataset or file may not be used. The message lists every problem found."""


def normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load_manifest(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text())
    if not isinstance(loaded, dict):
        raise ProvenanceError(f"{path}: manifest is not a mapping")
    return loaded


def _get(manifest: Mapping[str, Any], dotted: str) -> Any:
    node: Any = manifest
    for part in dotted.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _is_date(value: Any) -> bool:
    if isinstance(value, dt.date):
        return True
    try:
        dt.date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def manifest_problems(manifest: Mapping[str, Any]) -> list[str]:
    """Every reason this manifest must be refused (empty list = acceptable for research use)."""
    problems: list[str] = []
    name = str(manifest.get("name") or "")
    for key, reason in PROHIBITED_DATASETS.items():
        if key in normalise(name):
            problems.append(f"dataset {name!r} is prohibited: {reason}")
    for key in ("source.url", "source.mirror_url"):
        url = str(_get(manifest, key) or "")
        if any(prohibited in normalise(url) for prohibited in PROHIBITED_DATASETS):
            problems.append(f"{key} points at a prohibited source: {url}")
    for item in manifest.get("contains_third_party_from") or []:
        if any(key in normalise(str(item)) for key in PROHIBITED_DATASETS):
            problems.append(f"declares that it contains images from prohibited source {item!r}")

    for key in ("name", "version", "source.url", "source.version", "citation.text"):
        if _blank(_get(manifest, key)):
            problems.append(f"missing required field {key}")
    if not _is_date(_get(manifest, "accessed")):
        problems.append("missing or invalid `accessed` (download date, ISO 8601)")
    digest = str(_get(manifest, "images.files_digest") or "")
    if not _SHA256.match(digest):
        problems.append("images.files_digest must be a SHA-256 hex digest")

    problems += _licence_problems(manifest)
    problems += _label_problems(manifest)
    split = manifest.get("split")
    if not isinstance(split, Mapping) or _blank(split.get("method")) or "seed" not in split:
        problems.append("split.method and split.seed must be recorded")
    return problems


def _licence_problems(manifest: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    declared = _get(manifest, "licence.declared")
    if not isinstance(declared, list) or not declared:
        return ["licence.declared must list every licence statement found, with its source"]
    spdx: set[str] = set()
    for entry in declared:
        if not isinstance(entry, Mapping):
            problems.append("licence.declared entries must be mappings")
            continue
        value = str(entry.get("spdx") or "").strip()
        if value.lower() in _UNKNOWN_LICENCES:
            problems.append(f"licence from {entry.get('source')!r} is unknown")
        if _blank(entry.get("source")) or _blank(entry.get("evidence")):
            problems.append("every declared licence needs `source` and `evidence`")
        spdx.add(value)
    status = _get(manifest, "licence.status")
    if len(spdx) > 1 and status != "conflicting" and not _resolved(manifest):
        problems.append(
            f"sources declare different licences {sorted(spdx)}: status must be 'conflicting'"
        )
    if status not in {"verified", "conflicting", "resolved"}:
        problems.append("licence.status must be one of verified, conflicting, resolved")
    if not isinstance(_get(manifest, "licence.release_allowed"), bool):
        problems.append("licence.release_allowed must be an explicit true or false")
    elif _get(manifest, "licence.release_allowed") and status == "conflicting":
        problems.append("release_allowed cannot be true while the licence is conflicting")
    return problems


def _resolved(manifest: Mapping[str, Any]) -> bool:
    resolution = _get(manifest, "licence.resolution")
    return (
        isinstance(resolution, Mapping)
        and not _blank(resolution.get("evidence"))
        and _is_date(resolution.get("date"))
    )


def _label_problems(manifest: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    classes = _get(manifest, "labels.classes")
    if not isinstance(classes, list) or not classes:
        return ["labels.classes must list every source label with an explicit `maps_to`"]
    for entry in classes:
        if not isinstance(entry, Mapping) or "name" not in entry or "maps_to" not in entry:
            problems.append(f"label entry without name or explicit maps_to: {entry!r}")
            continue
        target = entry["maps_to"]
        catch_all = target is not None and _CATCH_ALL.search(str(entry["name"]))
        if catch_all and _blank(entry.get("mapping_justification")):
            problems.append(
                f"catch-all label {entry['name']!r} is mapped to {target!r} without a "
                "written mapping_justification"
            )
        if target is None and _blank(entry.get("reason")):
            problems.append(f"label {entry['name']!r} has no class and no recorded reason")
    return problems


def require_acceptable(manifest: Mapping[str, Any]) -> None:
    """Raise `ProvenanceError` unless the manifest may be used for research training/evaluation."""
    if problems := manifest_problems(manifest):
        raise ProvenanceError("dataset refused:\n  - " + "\n  - ".join(problems))


def release_allowed(manifest: Mapping[str, Any]) -> bool:
    """May a model trained on this dataset be released? Only with a verified or resolved licence."""
    if manifest_problems(manifest):
        return False
    status = _get(manifest, "licence.status")
    return bool(_get(manifest, "licence.release_allowed")) and status in _RELEASE_STATES


def label_map(manifest: Mapping[str, Any]) -> dict[str, str | None]:
    """Source folder -> EcoMind class (None = out of scope), straight from the manifest."""
    return {str(e["name"]): e["maps_to"] for e in manifest["labels"]["classes"]}


# -- content-level exclusion -----------------------------------------------------------------------
def load_denylist(path: Path = DENYLIST_FILE) -> frozenset[str]:
    """SHA-256 digests of files that may never appear in any dataset (hashes only, no images)."""
    if not path.is_file():
        raise ProvenanceError(f"denylist missing: {path} (failing closed)")
    digests = {
        line.split()[0].lower()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    bad = sorted(d for d in digests if not _SHA256.match(d))
    if bad:
        raise ProvenanceError(f"denylist contains malformed digests: {bad[:3]}")
    if not digests:
        raise ProvenanceError(f"denylist {path} is empty (failing closed)")
    return frozenset(digests)


def prohibited_files(hashes: Mapping[str, str], denylist: frozenset[str]) -> list[str]:
    """Keys (file names) whose content is on the denylist."""
    return sorted(key for key, digest in hashes.items() if digest.lower() in denylist)


def require_no_prohibited_files(hashes: Mapping[str, str], denylist: frozenset[str]) -> None:
    if found := prohibited_files(hashes, denylist):
        raise ProvenanceError(
            f"{len(found)} file(s) are byte-identical to a prohibited image, e.g. {found[:3]}"
        )


# -- leakage ---------------------------------------------------------------------------------------
def straddling_duplicates(hashes: Sequence[str], folds: NDArray[np.int_]) -> list[str]:
    """Digests of byte-identical files that sit in more than one fold."""
    seen: dict[str, set[int]] = defaultdict(set)
    for digest, fold in zip(hashes, folds, strict=True):
        seen[digest].add(int(fold))
    return sorted(d for d, f in seen.items() if len(f) > 1)


def require_no_leakage(hashes: Sequence[str], folds: NDArray[np.int_]) -> None:
    if leaks := straddling_duplicates(hashes, folds):
        raise ProvenanceError(
            f"{len(leaks)} byte-identical file(s) straddle two splits: {leaks[:3]}"
        )


def exact_duplicate_count(hashes: Iterable[str]) -> int:
    """Number of files that are an exact copy of an earlier file."""
    items = list(hashes)
    return len(items) - len(set(items))
