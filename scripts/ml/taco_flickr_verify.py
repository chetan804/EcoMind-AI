#!/usr/bin/env python3
"""Owner-run helper: read each TACO image's licence AT ITS SOURCE (Flickr) and record it.

TACO's own file says only "CC" or nothing for most images, which is not enough to show that commercial
use is allowed. Flickr, where the photographs were published, states the exact licence of each photo.
This script asks the Flickr API (``flickr.photos.getInfo``) for every image whose file name is a
Flickr photo id and writes ``datasets/external/taco/verification.csv``, which
``scripts/ml/taco_licence.py audit`` then uses in place of the annotation value.

Needs YOUR Flickr API key (https://www.flickr.com/services/api/misc.api_keys.html) in the environment
variable FLICKR_API_KEY and network access to api.flickr.com. Neither exists in the build sandbox, so
this script is tested with a mocked transport only. Nothing is written for a photo that Flickr no longer
returns; such images stay excluded.

    FLICKR_API_KEY=... python scripts/ml/taco_flickr_verify.py --annotations data/annotations.json

Flickr licence ids (documented for ``flickr.photos.licenses.getInfo``): 0 all rights reserved, 1 BY-NC-SA,
2 BY-NC, 3 BY-NC-ND, 4 BY, 5 BY-SA, 6 BY-ND, 7 no known copyright restrictions, 8 US government work,
9 CC0, 10 public domain mark. Newer CC 4.0 ids (11 and up) are NOT mapped here: they are recorded as
unmapped and stay excluded until you map them deliberately.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "datasets" / "external" / "taco" / "verification.csv"
API = "https://api.flickr.com/services/rest/"
LICENCE_BY_ID = {
    "0": "All Rights Reserved",
    "1": "CC BY-NC-SA 2.0",
    "2": "CC BY-NC 2.0",
    "3": "CC BY-NC-ND 2.0",
    "4": "CC BY 2.0",
    "5": "CC BY-SA 2.0",
    "6": "CC BY-ND 2.0",
    "7": "No known copyright restrictions",
    "8": "US Government Work",
    "9": "CC0 1.0",
    "10": "PDM 1.0",
}
FIELDS = ["image_id", "licence", "evidence_url", "verified_on", "verified_by"]
Get = Callable[[str], bytes]


def photo_id(flickr_url: str) -> str | None:
    """The numeric Flickr photo id when the file name is one (``.../33978196618.jpg``)."""
    match = re.search(r"/(\d{6,})(?:_[0-9a-f]+)?(?:_\w)?\.\w+$", flickr_url or "")
    return match.group(1) if match else None


def http_get(url: str) -> bytes:
    if not url.startswith("https://api.flickr.com/"):
        raise ValueError("only api.flickr.com is queried")
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return bytes(response.read(1_000_000))


def lookup(photo: str, api_key: str, get: Get) -> str | None:
    """Licence text for one photo, or None if Flickr did not return it (removed, private, error)."""
    query = urllib.parse.urlencode(
        {
            "method": "flickr.photos.getInfo",
            "api_key": api_key,
            "photo_id": photo,
            "format": "json",
            "nojsoncallback": "1",
        }
    )
    try:
        payload = json.loads(get(f"{API}?{query}"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("stat") != "ok":
        return None
    licence_id = str(payload.get("photo", {}).get("license", ""))
    return LICENCE_BY_ID.get(licence_id, f"unmapped Flickr licence id {licence_id}")


def run(args: argparse.Namespace, get: Get = http_get) -> int:
    api_key = os.environ.get("FLICKR_API_KEY", "")
    if not api_key:
        print("error: set FLICKR_API_KEY (your own Flickr API key)", file=sys.stderr)
        return 2
    data = json.loads(Path(args.annotations).read_text(encoding="utf-8"))
    out = Path(args.output)
    done: set[str] = set()
    if out.exists():
        with out.open(newline="", encoding="utf-8") as handle:
            done = {row["image_id"] for row in csv.DictReader(handle)}
    todo = [(str(i["id"]), photo_id(str(i.get("flickr_url") or ""))) for i in data["images"]]
    todo = [(image_id, photo) for image_id, photo in todo if photo and image_id not in done]
    if args.limit:
        todo = todo[: args.limit]
    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists()
    written = missing = 0
    today = datetime.now(UTC).date().isoformat()
    with out.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(FIELDS)
        for image_id, photo in todo:
            licence = lookup(str(photo), api_key, get)
            if licence is None:
                missing += 1
            else:
                writer.writerow(
                    [
                        image_id,
                        licence,
                        f"https://www.flickr.com/photo.gne?id={photo}",
                        today,
                        args.verified_by,
                    ]
                )
                written += 1
            handle.flush()
            time.sleep(args.pause)
    print(f"Recorded {written} licences, {missing} photos not returned by Flickr (stay excluded): {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--annotations", required=True, help="path to TACO data/annotations.json")
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--verified-by", default="project owner", help="name recorded in the evidence file")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--pause", type=float, default=1.1, help="seconds between calls (Flickr allows 3600/hour)"
    )
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
