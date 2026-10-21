"""TACO per-image Flickr licence evidence: the fetch tool (mocked transport), the validator and the audit.

No real Flickr answer has ever been seen by the author (api.flickr.com is unreachable from the build
environment): every answer below is a synthetic stand-in shaped like the documented API. These tests prove what
the scripts decide, not what Flickr says.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from datetime import date
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


flickr = load("taco_flickr_verify")
audit = load("taco_licence")
ev = sys.modules["taco_evidence"]

TABLE = {
    "stat": "ok",
    "licenses": {
        "license": [
            {"id": 0, "name": "All Rights Reserved", "url": ""},
            {"id": 2, "name": "Attribution-NonCommercial License", "url": "https://creativecommons.org/licenses/by-nc/2.0/"},
            {"id": 4, "name": "Attribution License", "url": "https://creativecommons.org/licenses/by/2.0/"},
            {"id": 5, "name": "Attribution-ShareAlike License", "url": "https://creativecommons.org/licenses/by-sa/2.0/"},
            {"id": 7, "name": "No known copyright restrictions", "url": "https://www.flickr.com/commons/usage/"},
            {"id": 9, "name": "Public Domain Dedication (CC0)", "url": "https://creativecommons.org/publicdomain/zero/1.0/"},
            {"id": 11, "name": "Attribution 4.0 International", "url": "https://creativecommons.org/licenses/by/4.0/"},
        ]
    },
}
PHOTOS = {  # photo id -> (licence id, owner)
    "111111111": ("4", "Alice A"),
    "222222222": ("11", "Bob B"),
    "333333333": ("0", "Carol C"),
    "444444444": ("2", "Dan D"),
    "555555555": ("9", "Eve E"),
    "666666666": ("7", "Frank F"),
}
TODAY = date(2026, 10, 21)


def photo_answer(photo: str) -> bytes:
    licence, owner = PHOTOS[photo]
    return json.dumps(
        {
            "stat": "ok",
            "photo": {
                "id": photo,
                "license": licence,
                "owner": {"nsid": "1@N01", "username": owner.lower().replace(" ", ""), "realname": owner},
                "urls": {"url": [{"type": "photopage", "_content": f"https://www.flickr.com/photos/x/{photo}/"}]},
            },
        }
    ).encode()


def annotations() -> dict[str, object]:
    def image(i: int, photo: str | None) -> dict[str, object]:
        url = f"https://img.tacodataset.org/img/{photo}.jpg" if photo else "https://olm-s3.example/1048/xyz"
        return {"id": i, "file_name": f"b/{i:06d}.jpg", "license": "CC", "flickr_url": url}

    photos = [*PHOTOS, "777777777", None]  # 777... is gone from Flickr; the last image is not on Flickr at all
    return {"images": [image(i, p) for i, p in enumerate(photos, start=1)], "annotations": []}


class World:
    """A fake Flickr plus the files a run leaves behind."""

    def __init__(self, tmp: Path) -> None:
        self.annotations = tmp / "annotations.json"
        self.annotations.write_text(json.dumps(annotations()), encoding="utf-8")
        self.out, self.raw = tmp / "verification.csv", tmp / "flickr_raw"
        self.calls: list[str] = []
        self.flaky: dict[str, int] = {}
        self.fatal = False

    def get(self, url: str) -> bytes:
        self.calls.append(url)
        if self.fatal:
            return b'{"stat":"fail","code":100,"message":"Invalid API Key"}'
        if "licenses.getInfo" in url:
            return json.dumps(TABLE).encode()
        photo = url.split("photo_id=")[1].split("&")[0]
        if self.flaky.get(photo, 0) > 0:
            self.flaky[photo] -= 1
            raise flickr.Transient("HTTP 503")
        if photo == "777777777":
            return b'{"stat":"fail","code":1,"message":"Photo not found"}'
        return photo_answer(photo)

    def args(self, **extra: object) -> argparse.Namespace:
        base = {
            "annotations": str(self.annotations),
            "output": str(self.out),
            "raw_dir": str(self.raw),
            "verified_by": "owner",
            "limit": 0,
            "pause": 0.0,
        }
        return argparse.Namespace(**{**base, **extra})

    def fetch(self) -> int:
        return int(flickr.fetch(self.args(), get=self.get))

    def validate(self, *, raw: bool = True) -> int:
        return int(
            flickr.validate(
                argparse.Namespace(
                    annotations=str(self.annotations),
                    verification=str(self.out),
                    raw_dir=str(self.raw) if raw else None,
                    report=None,
                )
            )
        )

    def rows(self) -> list[dict[str, str]]:
        with self.out.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def write_rows(self, rows: list[dict[str, str]]) -> None:
        with self.out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=ev.FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def audit(self, tmp: Path, *, raw: bool = True) -> tuple[dict[str, object], list[dict[str, str]]]:
        report, eligible = tmp / "report.json", tmp / "eligible.csv"
        argv = [
            "audit", "--annotations", str(self.annotations), "--verification", str(self.out),
            "--report", str(report), "--eligible", str(eligible), "--raw-dir", str(self.raw if raw else tmp / "absent"),
        ]  # fmt: skip
        assert audit.main(argv) == 0
        with eligible.open(newline="", encoding="utf-8") as handle:
            return json.loads(report.read_text()), list(csv.DictReader(handle))


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    monkeypatch.setenv("FLICKR_API_KEY", "test-key")
    monkeypatch.setattr(flickr.time, "sleep", lambda _s: None)
    return World(tmp_path)


# ------------------------------------------------------------------------------------- pure rules


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://creativecommons.org/licenses/by/2.0/", "CC BY 2.0"),
        ("http://creativecommons.org/licenses/by-sa/4.0", "CC BY-SA 4.0"),
        ("https://creativecommons.org/licenses/by-nc-nd/4.0/", "CC BY-NC-ND 4.0"),
        ("https://creativecommons.org/publicdomain/zero/1.0/", "CC0 1.0"),
        ("https://creativecommons.org/publicdomain/mark/1.0/", "PDM 1.0"),
        ("https://www.flickr.com/commons/usage/", None),
        ("https://creativecommons.org.evil.example/licenses/by/2.0/", None),
        ("https://creativecommons.org/licenses/by/2.0/extra", None),
        ("", None),
    ],
)
def test_licence_text_is_derived_only_from_a_creative_commons_url(url: str, expected: str | None) -> None:
    assert ev.licence_from_url(url) == expected


def test_unmapped_licences_are_never_eligible() -> None:
    text = ev.derive_licence("7", "No known copyright restrictions", "https://www.flickr.com/commons/usage/")
    assert text.startswith("unmapped Flickr licence 7")
    assert audit.classify(text) == "unknown"
    assert audit.classify(ev.derive_licence("0", "All Rights Reserved", "")) == "unknown"
    assert audit.classify("unavailable (Flickr error 1)") == "unknown"


def test_the_licence_table_must_look_like_flickrs() -> None:
    assert ev.parse_licence_table(json.dumps(TABLE))["11"]["url"].endswith("/by/4.0/")
    for bad in ('{"stat":"fail","code":100}', '{"stat":"ok","licenses":{"license":[]}}', "[]"):
        with pytest.raises(ValueError):
            ev.parse_licence_table(bad)


def test_photo_ids_come_from_flickr_style_file_names() -> None:
    assert ev.photo_id("https://img.tacodataset.org/img/33978196618.jpg") == "33978196618"
    assert ev.photo_id("https://farm5.staticflickr.com/4864/31761220157_927fea50b6_o.png") == "31761220157"
    assert ev.photo_id("https://olm-s3.s3.eu-west-1.amazonaws.com/1048/vPr8VJAbWN8OV") is None
    assert ev.photo_id("") is None


def test_transport_only_talks_to_the_flickr_api() -> None:
    with pytest.raises(ValueError, match="api.flickr.com"):
        flickr.http_get("https://example.org/services/rest/")


# ------------------------------------------------------------------------------------------ fetch


def test_fetch_needs_a_key(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLICKR_API_KEY")
    assert world.fetch() == 2
    assert world.calls == []


def test_fetch_records_each_photo_with_its_licence_owner_and_raw_answer(world: World) -> None:
    assert world.fetch() == 0
    rows = {r["image_id"]: r for r in world.rows()}
    assert [rows[str(i)]["licence"] for i in (1, 2, 4, 5)] == ["CC BY 2.0", "CC BY 4.0", "CC BY-NC 2.0", "CC0 1.0"]
    assert rows["3"]["licence"].startswith("unmapped Flickr licence 0")
    assert rows["6"]["licence"].startswith("unmapped Flickr licence 7")
    assert rows["7"]["licence"] == "unavailable (Flickr error 1)"
    assert "8" not in rows  # not a Flickr photo: nothing to ask, nothing recorded
    assert rows["1"]["owner"] == "Alice A"
    assert rows["1"]["evidence_url"] == "https://www.flickr.com/photo.gne?id=111111111"
    assert rows["1"]["source"] == "flickr.photos.getInfo"
    assert (world.raw / "111111111.json").read_bytes() == photo_answer("111111111")
    assert (world.raw / "licenses.json").is_file()
    assert ev.sha256_hex((world.raw / "111111111.json").read_bytes()) == rows["1"]["raw_sha256"]


def test_fetch_output_passes_validation_against_the_raw_answers(world: World) -> None:
    assert world.fetch() == 0
    assert world.validate() == 0
    assert world.validate(raw=False) == 0


def test_a_rerun_does_not_ask_again_for_recorded_photos(world: World) -> None:
    world.fetch()
    before = len(world.calls)
    assert world.fetch() == 0
    assert len(world.calls) == before + 1  # only the licence table is re-read


def test_transient_failures_are_retried_and_if_they_persist_not_recorded(world: World) -> None:
    world.flaky = {"111111111": 2, "222222222": 99}
    assert world.fetch() == 0
    ids = {r["image_id"] for r in world.rows()}
    assert "1" in ids  # succeeded on the third attempt
    assert "2" not in ids  # never answered: not recorded, so a re-run asks again
    world.flaky = {}
    assert world.fetch() == 0
    assert "2" in {r["image_id"] for r in world.rows()}


def test_a_bad_api_key_stops_the_run(world: World) -> None:
    world.fatal = True
    assert world.fetch() == 3
    assert not world.out.exists() or world.rows() == []


def test_without_the_licence_table_nothing_is_verified(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    def broken(url: str) -> bytes:
        raise flickr.Transient("offline")

    assert flickr.fetch(world.args(), get=broken) == 3
    assert "licence table" in capsys.readouterr().err


def test_limit_caps_the_number_of_photos_asked(world: World) -> None:
    assert int(flickr.fetch(world.args(limit=2), get=world.get)) == 0
    assert len(world.rows()) == 2


# --------------------------------------------------------------------------------------- validator


def tamper(world: World, image_id: str, **changes: str) -> None:
    rows = world.rows()
    for row in rows:
        if row["image_id"] == image_id:
            row.update(changes)
    world.write_rows(rows)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"licence": "CC BY 2.0"}, "unmapped"),  # image 3 is all-rights-reserved: relabelling it must fail
        ({"licence_url": "https://creativecommons.org/licenses/by/2.0/"}, "licence"),
        ({"evidence_url": "https://www.flickr.com/photo.gne?id=222222222"}, "evidence_url"),
        ({"verified_on": "2999-01-01"}, "future"),
        ({"verified_on": "yesterday"}, "ISO date"),
        ({"verified_by": ""}, "verified_by"),
        ({"source": "hand-typed"}, "source"),
    ],
)
def test_tampered_rows_are_rejected(world: World, capsys: pytest.CaptureFixture[str], changes: dict[str, str], message: str) -> None:
    world.fetch()
    tamper(world, "3", **changes)
    assert world.validate() == 1
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"licence": "CC BY-NC 2.0", "licence_id": "2", "licence_url": "https://creativecommons.org/licenses/by-nc/2.0/"}, "differs"),
        ({"owner": "Somebody Else"}, "owner differs"),
        ({"licence": "CC BY 4.0"}, "does not match"),
        ({"owner": ""}, "owner"),
        ({"photo_url": "https://www.flickr.com/photos/x/999999999/"}, "photo_url"),
        ({"raw_sha256": "0" * 64}, "raw_sha256"),
        ({"licence_id": "x"}, "number"),
    ],
)
def test_a_forged_cc_by_row_is_caught_by_the_checks(world: World, capsys: pytest.CaptureFixture[str], changes: dict[str, str], message: str) -> None:
    world.fetch()
    tamper(world, "1", **changes)
    assert world.validate() == 1
    assert message in capsys.readouterr().err


def test_editing_the_raw_answer_after_the_fact_is_detected(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    world.fetch()
    (world.raw / "111111111.json").write_bytes(photo_answer("222222222"))
    assert world.validate() == 1
    assert "raw_sha256" in capsys.readouterr().err
    (world.raw / "111111111.json").unlink()
    assert world.validate() == 1
    assert "missing" in capsys.readouterr().err


def test_a_forged_licence_url_is_caught_against_flickrs_saved_table(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    world.fetch()
    tamper(world, "4", licence="CC BY 2.0", licence_url="https://creativecommons.org/licenses/by/2.0/")
    assert world.validate() == 1  # image 4 is really BY-NC (id 2)
    assert "differs" in capsys.readouterr().err
    assert "differs" not in capsys.readouterr().err
    assert world.validate(raw=False) == 1  # offline, the documented id-to-URL table still exposes it
    assert "documents for this licence id" in capsys.readouterr().err


def test_structural_problems_are_reported(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    world.fetch()
    rows = world.rows()
    world.write_rows([*rows, rows[0]])  # a duplicate
    assert world.validate() == 1
    assert "more than once" in capsys.readouterr().err
    world.write_rows([*rows, {**rows[0], "image_id": "999"}])  # an unknown image
    assert world.validate() == 1
    assert "not in the annotation file" in capsys.readouterr().err
    world.write_rows([{**rows[0], "image_id": "8"}])  # image 8 has no Flickr id
    assert world.validate() == 1
    assert "no Flickr photo id" in capsys.readouterr().err
    world.out.write_text("image_id,licence\n1,CC BY 2.0\n", encoding="utf-8")  # old/foreign columns
    assert world.validate() == 1
    assert "columns" in capsys.readouterr().err
    world.out.unlink()
    assert world.validate() == 2


# ------------------------------------------------------------------------------------------ audit


def test_audit_accepts_validated_rows_and_nothing_else(world: World, tmp_path: Path) -> None:
    world.fetch()
    report, eligible = world.audit(tmp_path)
    assert {r["image_id"] for r in eligible} == {"1", "2", "5"}  # CC BY 2.0, CC BY 4.0, CC0
    by_id = {r["image_id"]: r for r in eligible}
    assert by_id["1"]["owner"] == "Alice A"
    assert by_id["1"]["photo_url"] == "https://www.flickr.com/photos/x/111111111/"
    assert report["eligible_images"] == 3
    assert report["verification_rows_rejected"] == 0
    assert report["verification_compared_with_raw_flickr_answers"] is True
    assert report["images_by_category"]["noncommercial"] == 1  # image 4, BY-NC
    assert "url" not in json.dumps(report)


def test_audit_ignores_rows_that_fail_validation(world: World, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    world.fetch()
    tamper(world, "3", licence="CC BY 2.0", licence_id="4", licence_url="https://creativecommons.org/licenses/by/2.0/")
    report, eligible = world.audit(tmp_path)
    assert "3" not in {r["image_id"] for r in eligible}  # the forged row did not make an all-rights-reserved photo eligible
    assert report["verification_rows_rejected"] == 1
    assert "ignored" in capsys.readouterr().err


def test_audit_never_takes_a_tool_row_for_an_unknown_image(world: World, tmp_path: Path) -> None:
    world.fetch()
    rows = world.rows()
    world.write_rows([{**rows[0], "image_id": "999"}])
    report, eligible = world.audit(tmp_path)
    assert eligible == []
    assert report["verification_rows_rejected"] == 1


def test_audit_without_the_raw_folder_still_applies_the_structural_rules(world: World, tmp_path: Path) -> None:
    world.fetch()
    report, eligible = world.audit(tmp_path, raw=False)
    assert report["verification_compared_with_raw_flickr_answers"] is False
    assert {r["image_id"] for r in eligible} == {"1", "2", "5"}
    tamper(world, "4", evidence_url="https://www.flickr.com/photo.gne?id=111111111")
    report, _ = world.audit(tmp_path, raw=False)
    assert report["verification_rows_rejected"] == 1


def test_a_missing_licence_table_rejects_every_row_when_raw_answers_exist(world: World, tmp_path: Path) -> None:
    world.fetch()
    (world.raw / "licenses.json").unlink()
    report, eligible = world.audit(tmp_path)
    assert eligible == []
    assert report["verification_rows_rejected"] >= 5


def test_nothing_is_eligible_when_no_evidence_file_exists(world: World, tmp_path: Path) -> None:
    report, eligible = world.audit(tmp_path)
    assert eligible == []  # TACO's own "CC" strings prove nothing
    assert report["eligible_images"] == 0
