"""Shared rules for TACO per-image licence evidence (used by taco_flickr_verify.py and taco_licence.py).

The evidence is a CSV written by ``taco_flickr_verify.py fetch`` from Flickr's own API answer for each
photograph, plus (optionally) the raw API answers it was derived from. This module decides whether a row
is acceptable. It checks that a row is internally consistent, bound to the right image, correctly derived
from the licence URL Flickr reported and, when the raw answers are available, identical to them.

What this can and cannot show (see docs/ml/dataset-research/TACO_LICENCE_AUDIT.md): a file that passes proves
the rows agree with each other and with the saved raw answers. It cannot prove that the answers came from
Flickr: anyone able to write the CSV and the raw files could forge both. The protection against that is
procedural: the owner runs ``fetch`` themselves, with their own API key, and keeps the raw directory.

Standard library only; no network.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

SOURCE = "flickr.photos.getInfo"
FIELDS = [
    "image_id",
    "licence",
    "licence_id",
    "licence_url",
    "evidence_url",
    "photo_url",
    "owner",
    "raw_sha256",
    "verified_on",
    "verified_by",
    "source",
]
LICENCE_TABLE_FILE = "licenses.json"
UNAVAILABLE = re.compile(r"^unavailable \(Flickr error (1|2)\)$")
# Flickr's documented ids 0-10 (flickr.photos.licenses.getInfo; 9 and 10 were added in 2015). Ids from 11 up (the
# Creative Commons 4.0 licences, 2025) are NOT listed: they are checked only against the saved live table.
STATIC_ID_PATHS = {
    "1": "licenses/by-nc-sa/2.0",
    "2": "licenses/by-nc/2.0",
    "3": "licenses/by-nc-nd/2.0",
    "4": "licenses/by/2.0",
    "5": "licenses/by-sa/2.0",
    "6": "licenses/by-nd/2.0",
    "9": "publicdomain/zero/1.0",
    "10": "publicdomain/mark/1.0",
}
_CC_URL = re.compile(
    r"^https?://creativecommons\.org/licenses/(by|by-sa|by-nc|by-nc-sa|by-nd|by-nc-nd)/(\d\.\d)/?$"
)
_CC0_URL = re.compile(r"^https?://creativecommons\.org/publicdomain/zero/(\d\.\d)/?$")
_PDM_URL = re.compile(r"^https?://creativecommons\.org/publicdomain/mark/(\d\.\d)/?$")
_PHOTO_FILE = re.compile(r"/(\d{6,})(?:_[0-9a-f]+)?(?:_\w)?\.\w+$")
_NUMERIC = re.compile(r"^\d{6,}$")


def photo_id(flickr_url: str) -> str | None:
    """The numeric Flickr photo id when the file name is one (``.../33978196618.jpg``)."""
    match = _PHOTO_FILE.search(flickr_url or "")
    return match.group(1) if match else None


def evidence_url(photo: str) -> str:
    return f"https://www.flickr.com/photo.gne?id={photo}"


def licence_from_url(url: str) -> str | None:
    """``https://creativecommons.org/licenses/by-sa/4.0/`` -> ``CC BY-SA 4.0``; None if not a CC/PD URL."""
    cc = _CC_URL.match(url or "")
    if cc:
        return f"CC {cc.group(1).upper()} {cc.group(2)}"
    zero = _CC0_URL.match(url or "")
    if zero:
        return f"CC0 {zero.group(1)}"
    mark = _PDM_URL.match(url or "")
    if mark:
        return f"PDM {mark.group(1)}"
    return None


def derive_licence(licence_id: str, name: str, url: str) -> str:
    """The licence text recorded for a Flickr licence. Anything that is not a recognised Creative Commons
    or public-domain URL (all rights reserved, US government work, 'no known copyright restrictions', a
    future id) is recorded as unmapped, which the audit then excludes."""
    return licence_from_url(url) or f"unmapped Flickr licence {licence_id}: {name or 'unnamed'}"


def parse_licence_table(raw: bytes | str) -> dict[str, dict[str, str]]:
    """Flickr's ``flickr.photos.licenses.getInfo`` answer as ``{id: {"name": ..., "url": ...}}``."""
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("stat") != "ok":
        raise ValueError("the licence table is not a successful Flickr answer")
    items = payload.get("licenses", {}).get("license", [])
    table = {
        str(item["id"]): {"name": str(item.get("name", "")), "url": str(item.get("url", ""))}
        for item in items
        if isinstance(item, dict) and "id" in item
    }
    if "4" not in table or "0" not in table:
        raise ValueError("the licence table lacks the standard entries (0, 4); refusing to use it")
    return table


@dataclass(frozen=True)
class PhotoInfo:
    photo_id: str
    licence_id: str
    owner: str
    photo_url: str


def parse_photo_info(raw: bytes | str) -> PhotoInfo:
    """Read ``flickr.photos.getInfo``; raises ValueError unless it is a successful answer for one photo."""
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("stat") != "ok":
        raise ValueError("not a successful Flickr answer")
    photo = payload.get("photo")
    if not isinstance(photo, dict) or "license" not in photo or not str(photo.get("id", "")):
        raise ValueError("the answer has no photo with a licence")
    owner_block = photo.get("owner") if isinstance(photo.get("owner"), dict) else {}
    owner = str(owner_block.get("realname") or owner_block.get("username") or "").strip()
    urls = photo.get("urls", {}).get("url", []) if isinstance(photo.get("urls"), dict) else []
    page = next(
        (u.get("_content", "") for u in urls if isinstance(u, dict) and u.get("type") == "photopage"), ""
    )
    return PhotoInfo(str(photo["id"]), str(photo["license"]), owner, str(page))


def flickr_error_code(raw: bytes | str) -> int | None:
    """The numeric code of a Flickr ``stat: fail`` answer, else None."""
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if isinstance(payload, dict) and payload.get("stat") == "fail":
        try:
            return int(payload.get("code"))
        except (TypeError, ValueError):
            return None
    return None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_row(
    row: Mapping[str, str],
    image: Mapping[str, Any] | None,
    *,
    today: date,
    raw_dir: Path | None = None,
    table: Mapping[str, Mapping[str, str]] | None = None,
) -> list[str]:
    """Problems with one evidence row (empty list = acceptable)."""
    problems: list[str] = []
    if image is None:
        return ["the image id is not in the annotation file"]
    photo = photo_id(str(image.get("flickr_url") or ""))
    if photo is None:
        return ["the image has no Flickr photo id, so its licence cannot be checked at Flickr"]
    if row.get("source") != SOURCE:
        problems.append(f"source is not {SOURCE!r}")
    if row.get("evidence_url") != evidence_url(photo):
        problems.append("evidence_url does not point at this image's Flickr photo")
    if not (row.get("verified_by") or "").strip():
        problems.append("verified_by is empty")
    try:
        verified_on = date.fromisoformat(row.get("verified_on") or "")
        if verified_on > today:
            problems.append("verified_on is in the future")
    except ValueError:
        problems.append("verified_on is not an ISO date")
    licence = (row.get("licence") or "").strip()
    if UNAVAILABLE.match(licence):
        # Flickr no longer shows the photo: the rights cannot be established today, so it stays excluded.
        for field in ("licence_id", "licence_url", "owner"):
            if (row.get(field) or "").strip():
                problems.append(f"{field} must be empty for an unavailable photo")
        return problems + _check_raw(row, photo, licence, raw_dir, table, unavailable=True)
    licence_id, url = (row.get("licence_id") or "").strip(), (row.get("licence_url") or "").strip()
    if not licence_id.isdigit():
        problems.append("licence_id is not a number")
    if url and not url.startswith(("https://", "http://")):
        problems.append("licence_url is not a URL")
    expected = derive_licence(licence_id, "", url)
    static = STATIC_ID_PATHS.get(licence_id)
    if static is not None and re.sub(r"^https?://|/$", "", url) != f"creativecommons.org/{static}":
        problems.append("licence_url is not the one Flickr documents for this licence id")
    if licence_from_url(url) is not None:
        if licence != expected:
            problems.append("licence does not match the licence URL")
    elif not licence.startswith(f"unmapped Flickr licence {licence_id}"):
        problems.append("a licence without a Creative Commons or public-domain URL must be recorded as unmapped")
    photo_page = (row.get("photo_url") or "").strip()
    if licence_from_url(url) is not None:
        if not (row.get("owner") or "").strip():
            problems.append("owner is empty (CC BY and CC BY-SA need the author's name)")
        if not re.fullmatch(rf"https://www\.flickr\.com/photos/[^/\s]+/{photo}/?", photo_page):
            problems.append("photo_url is not this photo's Flickr page")
    return problems + _check_raw(row, photo, licence, raw_dir, table, unavailable=False)


def _check_raw(
    row: Mapping[str, str],
    photo: str,
    licence: str,
    raw_dir: Path | None,
    table: Mapping[str, Mapping[str, str]] | None,
    *,
    unavailable: bool,
) -> list[str]:
    """Compare the row with the saved raw Flickr answer (only when the raw directory is available)."""
    if raw_dir is None:
        return []
    path = raw_dir / f"{photo}.json"
    if not path.is_file():
        return ["the saved raw Flickr answer is missing"]
    data = path.read_bytes()
    if sha256_hex(data) != (row.get("raw_sha256") or ""):
        return ["raw_sha256 does not match the saved raw Flickr answer"]
    if unavailable:
        code = flickr_error_code(data)
        return [] if code is not None and licence == f"unavailable (Flickr error {code})" else [
            "the raw answer is not the Flickr error the row claims"
        ]
    try:
        info = parse_photo_info(data)
    except ValueError as error:
        return [f"the raw answer is unusable ({error})"]
    problems: list[str] = []
    if info.photo_id != photo:
        problems.append("the raw answer is for a different photo")
    if info.licence_id != (row.get("licence_id") or "").strip():
        problems.append("licence_id differs from the raw answer")
    if info.owner != (row.get("owner") or "").strip():
        problems.append("owner differs from the raw answer")
    if info.photo_url != (row.get("photo_url") or "").strip() and (row.get("photo_url") or "").strip():
        problems.append("photo_url differs from the raw answer")
    if table is None:
        problems.append("the saved licence table is missing, so the licence URL cannot be confirmed")
    else:
        entry = table.get(info.licence_id)
        if entry is None or entry["url"] != (row.get("licence_url") or "").strip():
            problems.append("licence_url differs from Flickr's licence table")
    return problems
