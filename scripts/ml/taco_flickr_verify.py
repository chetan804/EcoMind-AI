#!/usr/bin/env python3
"""Owner-run: read each TACO image's licence AT ITS SOURCE (Flickr), keep the evidence, and validate it.

TACO's own file says only "CC" or nothing for most images, which is not enough to show that commercial use
is allowed. Flickr, where the photographs were published, states the exact licence of every photo. Two
subcommands:

  fetch     For every image whose file name is a Flickr photo id, ask ``flickr.photos.getInfo`` for its
            licence and owner. Writes ``datasets/external/taco/verification.csv`` (one row per photo) and
            keeps Flickr's raw answer for each photo in ``datasets/external/taco/flickr_raw/`` (git-ignored;
            it names photographers), so a reviewer can check the CSV against what Flickr actually said.
            The licence table is read live from ``flickr.photos.licenses.getInfo`` rather than hard-coded
            (Flickr added Creative Commons 4.0 ids in 2025), and the licence text is derived from the
            licence's creativecommons.org URL. Anything else (all rights reserved, "no known copyright
            restrictions", US government work, an unknown id) is recorded as unmapped and stays excluded.
            A photo Flickr no longer returns (error 1 or 2) is recorded as "unavailable" and stays excluded.
            Transient failures are retried and, if they persist, NOT recorded, so a re-run asks again.
  validate  Check that file without any network: each row is bound to the right image, correctly derived,
            dated, attributed and (with the raw directory) identical to the saved Flickr answer. Exits 1
            if any row fails. ``taco_licence.py audit`` applies the same rules and ignores failing rows.

Needs YOUR Flickr API key (free: https://www.flickr.com/services/api/misc.api_keys.html) in FLICKR_API_KEY and
access to api.flickr.com. The build sandbox has neither, so ``fetch`` has only been tested with a mocked
transport; no real Flickr answer has been seen by the author.

    FLICKR_API_KEY=... python scripts/ml/taco_flickr_verify.py fetch --annotations data/annotations.json
    python scripts/ml/taco_flickr_verify.py validate --annotations data/annotations.json

Running it elsewhere (a machine that can reach Flickr) and bringing the result back: see
docs/ml/dataset-research/TACO_LICENCE_AUDIT.md, "Running the verification on another machine".
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taco_evidence as ev  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "datasets" / "external" / "taco"
OUT = EXTERNAL / "verification.csv"
RAW = EXTERNAL / "flickr_raw"
API = "https://api.flickr.com/services/rest/"
FATAL_CODES = {95, 96, 97, 98, 100, 105, 111, 112, 114, 115, 116}  # key/signature/service problems
RETRIES = 3
Get = Callable[[str], bytes]


class Transient(Exception):
    """A failure that may go away on its own (network error, rate limit, 5xx)."""


class Fatal(Exception):
    """A failure that retrying will not fix (bad API key, service disabled)."""


def http_get(url: str) -> bytes:
    if not url.startswith("https://api.flickr.com/"):
        raise ValueError("only api.flickr.com is queried")
    request = urllib.request.Request(url, headers={"User-Agent": "EcoMind-AI dataset audit"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return bytes(response.read(1_000_000))
    except urllib.error.HTTPError as error:
        raise Transient(f"HTTP {error.code}") from error
    except (urllib.error.URLError, OSError) as error:
        raise Transient(str(error)) from error


def call(method: str, api_key: str, get: Get, pause: float, **params: str) -> bytes:
    """One API call with retries on transient failures; returns Flickr's raw answer (ok or fail)."""
    query = urllib.parse.urlencode(
        {"method": method, "api_key": api_key, "format": "json", "nojsoncallback": "1", **params}
    )
    last = ""
    for attempt in range(RETRIES):
        try:
            raw = get(f"{API}?{query}")
        except Transient as error:
            last = str(error)
            time.sleep(pause * (2**attempt))
            continue
        code = ev.flickr_error_code(raw)
        if code in FATAL_CODES:
            raise Fatal(f"Flickr error {code}: check FLICKR_API_KEY and your key's status")
        if code is not None and code not in (1, 2):
            last = f"Flickr error {code}"
            time.sleep(pause * (2**attempt))
            continue
        try:
            json.loads(raw)
        except ValueError:
            last = "answer is not JSON"
            time.sleep(pause * (2**attempt))
            continue
        return raw
    raise Transient(last or "no answer")


def fetch(args: argparse.Namespace, get: Get = http_get) -> int:
    api_key = os.environ.get("FLICKR_API_KEY", "")
    if not api_key:
        print("error: set FLICKR_API_KEY (your own Flickr API key)", file=sys.stderr)
        return 2
    data = json.loads(Path(args.annotations).read_text(encoding="utf-8"))
    out, raw_dir = Path(args.output), Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    try:
        table_raw = call("flickr.photos.licenses.getInfo", api_key, get, args.pause)
        table = ev.parse_licence_table(table_raw)
    except Fatal as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except (Transient, ValueError) as error:
        print(f"error: cannot read Flickr's licence table ({error}); nothing can be verified", file=sys.stderr)
        return 3
    (raw_dir / ev.LICENCE_TABLE_FILE).write_bytes(table_raw)

    done: set[str] = set()
    if out.exists():
        with out.open(newline="", encoding="utf-8") as handle:
            done = {row["image_id"] for row in csv.DictReader(handle)}
    todo = [(str(i["id"]), ev.photo_id(str(i.get("flickr_url") or ""))) for i in data["images"]]
    todo = [(image_id, photo) for image_id, photo in todo if photo and image_id not in done]
    if args.limit:
        todo = todo[: args.limit]
    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists()
    counts: Counter[str] = Counter()
    today = datetime.now(UTC).date().isoformat()
    with out.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(ev.FIELDS)
        for image_id, photo in todo:
            try:
                raw = call(
                    "flickr.photos.getInfo", api_key, get, args.pause, photo_id=str(photo)
                )
            except Fatal as error:
                print(f"error: {error}", file=sys.stderr)
                return 3
            except Transient:
                counts["not_recorded_transient"] += 1
                continue
            row = _row(image_id, str(photo), raw, table, today, args.verified_by)
            if row is None:
                counts["not_recorded_unreadable"] += 1
                continue
            (raw_dir / f"{photo}.json").write_bytes(raw)
            writer.writerow([row[field] for field in ev.FIELDS])
            counts["unavailable" if ev.UNAVAILABLE.match(row["licence"]) else "recorded"] += 1
            handle.flush()
            time.sleep(args.pause)
    print(
        f"Recorded {counts['recorded']} licences, {counts['unavailable']} unavailable at Flickr (excluded), "
        f"{counts['not_recorded_transient'] + counts['not_recorded_unreadable']} not recorded (re-run to retry): {out}"
    )
    return 0


def _row(
    image_id: str, photo: str, raw: bytes, table: dict[str, dict[str, str]], today: str, verified_by: str
) -> dict[str, str] | None:
    base = {
        "image_id": image_id,
        "raw_sha256": ev.sha256_hex(raw),
        "evidence_url": ev.evidence_url(photo),
        "verified_on": today,
        "verified_by": verified_by,
        "source": ev.SOURCE,
    }
    code = ev.flickr_error_code(raw)
    if code in (1, 2):
        return {
            **base,
            "licence": f"unavailable (Flickr error {code})",
            "licence_id": "",
            "licence_url": "",
            "photo_url": "",
            "owner": "",
        }
    try:
        info = ev.parse_photo_info(raw)
    except ValueError:
        return None
    if info.photo_id != photo:
        return None
    entry = table.get(info.licence_id, {"name": "", "url": ""})
    return {
        **base,
        "licence": ev.derive_licence(info.licence_id, entry["name"], entry["url"]),
        "licence_id": info.licence_id,
        "licence_url": entry["url"],
        "photo_url": info.photo_url,
        "owner": info.owner,
    }


def validate(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.annotations).read_text(encoding="utf-8"))
    images = {str(i["id"]): i for i in data["images"]}
    path = Path(args.verification)
    if not path.is_file():
        print(f"error: {path} does not exist", file=sys.stderr)
        return 2
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ev.FIELDS:
            print(f"error: columns must be exactly {','.join(ev.FIELDS)}", file=sys.stderr)
            return 1
        rows = list(reader)
    raw_dir = Path(args.raw_dir) if args.raw_dir else None
    table = None
    if raw_dir is not None:
        try:
            table = ev.parse_licence_table((raw_dir / ev.LICENCE_TABLE_FILE).read_bytes())
        except (OSError, ValueError) as error:
            print(f"error: cannot read the saved licence table ({error})", file=sys.stderr)
            return 1
    today = datetime.now(UTC).date()
    seen: Counter[str] = Counter(row["image_id"] for row in rows)
    failures: dict[str, list[str]] = {}
    for row in rows:
        problems = ev.validate_row(row, images.get(row["image_id"]), today=today, raw_dir=raw_dir, table=table)
        if seen[row["image_id"]] > 1:
            problems.append("the image appears more than once")
        if problems:
            failures[row["image_id"]] = problems
    wanted = {i for i, image in images.items() if ev.photo_id(str(image.get("flickr_url") or ""))}
    summary = {
        "rows": len(rows),
        "valid_rows": len(rows) - len(failures),
        "invalid_rows": len(failures),
        "images_with_a_flickr_id": len(wanted),
        "images_without_a_row": len(wanted - set(seen)),
        "raw_answers_checked": raw_dir is not None,
        "licences": dict(Counter(row["licence"] for row in rows if row["image_id"] not in failures).most_common()),
        "verification_sha256": ev.sha256_hex(path.read_bytes()),
    }
    print(json.dumps(summary, indent=2))
    for image_id, problems in list(failures.items())[:20]:
        print(f"image {image_id}: {'; '.join(problems)}", file=sys.stderr)
    if args.report:
        Path(args.report).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if failures:
        print(f"error: {len(failures)} row(s) failed validation; the audit will ignore them", file=sys.stderr)
        return 1
    if not raw_dir:
        print("note: no --raw-dir given, so the rows were not compared with Flickr's saved answers", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fetch", help="read each photo's licence from Flickr (needs FLICKR_API_KEY)")
    p.add_argument("--annotations", required=True, help="path to TACO data/annotations.json")
    p.add_argument("--output", default=str(OUT))
    p.add_argument("--raw-dir", default=str(RAW), help="where Flickr's raw answers are kept")
    p.add_argument("--verified-by", default="project owner", help="name recorded in the evidence file")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--pause", type=float, default=1.1, help="seconds between calls (Flickr allows 3600/hour)")
    p.set_defaults(handler=fetch)
    p = sub.add_parser("validate", help="check a verification file offline")
    p.add_argument("--annotations", required=True)
    p.add_argument("--verification", default=str(OUT))
    p.add_argument("--raw-dir", nargs="?", const=str(RAW), default=None, help="also compare with the saved raw answers")
    p.add_argument("--report", help="write the summary JSON here")
    p.set_defaults(handler=validate)
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
