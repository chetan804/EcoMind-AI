"""scripts/maps/build_region_data.py: command construction, input checks and validators.

Planetiler, osmium, Docker and OSRM are NOT run here (the CI image has none of them); the tests prove what the
script itself decides: which commands it would run, what it refuses, and what its validators accept. The
MBTiles and OSRM answers below are synthetic stand-ins, not real map data.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sqlite3
import urllib.error
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "maps" / "build_region_data.py"
spec = importlib.util.spec_from_file_location("build_region_data", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

AOI = (78.2, 17.2, 78.65, 17.6)
OSM_ATTRIBUTION = (
    '<a href="https://www.openmaptiles.org/">&copy; OpenMapTiles</a> '
    '<a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>'
)


def make_mbtiles(
    path: Path,
    *,
    tile_format: str = "pbf",
    layers: tuple[str, ...] = ("transportation", "place", "water", "landuse"),
    bounds: str = "78.2,17.2,78.65,17.6",
    attribution: str = OSM_ATTRIBUTION,
    tiles: int = 3,
) -> Path:
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE metadata (name TEXT, value TEXT);"
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);"
    )
    metadata = {
        "name": "OpenMapTiles",
        "format": tile_format,
        "minzoom": "0",
        "maxzoom": "2",
        "bounds": bounds,
        "attribution": attribution,
        "json": json.dumps({"vector_layers": [{"id": name} for name in layers]}),
    }
    connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
    for z in range(tiles):
        connection.execute("INSERT INTO tiles VALUES (?, 0, 0, ?)", (z, gzip.compress(f"t{z}".encode())))
    connection.commit()
    connection.close()
    return path


# --------------------------------------------------------------------------- arguments and commands


def test_area_of_interest_is_read_from_the_project_file() -> None:
    assert mod.aoi_bbox() == AOI


@pytest.mark.parametrize("value", ["", "1,2,3", "a,b,c,d", "10,5,5,6", "78,18,79,17", "-181,0,1,1", "0,-91,1,1"])
def test_bad_bounding_boxes_are_refused(value: str) -> None:
    with pytest.raises(mod.StepError):
        mod.parse_bbox(value)


def test_good_bounding_box_round_trips() -> None:
    assert mod.parse_bbox("78.2,17.2,78.65,17.6") == AOI
    assert mod.bbox_text(AOI) == "78.2,17.2,78.65,17.6"


@pytest.mark.parametrize("region", ["", "..", "asia/../etc", "asia//india", "asia/in dia", "asia/india?x=1", "https://x"])
def test_region_paths_cannot_escape_the_geofabrik_host(region: str) -> None:
    with pytest.raises(mod.StepError):
        mod.geofabrik_url(region)


def test_default_region_is_the_southern_zone_extract() -> None:
    assert mod.geofabrik_url(mod.DEFAULT_REGION) == (
        "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf"
    )


def test_jvm_heap_follows_planetilers_half_the_input_rule() -> None:
    assert mod.jvm_memory_gb(100 * 1024**2) == 1
    assert mod.jvm_memory_gb(532 * 1024**2) == 1
    assert mod.jvm_memory_gb(6 * 1024**3) == 3


def test_planetiler_docker_command_mounts_only_the_work_folder(tmp_path: Path) -> None:
    command, cwd = mod.planetiler_command(
        "docker",
        work=tmp_path,
        osm=tmp_path / "in.osm.pbf",
        output=tmp_path / "region.mbtiles",
        bounds=AOI,
        maxzoom=14,
        memory_gb=2,
    )
    assert command[:3] == ["docker", "run", "--rm"]
    assert f"{tmp_path.resolve()}:/data" in command
    assert command.count("-v") == 1
    assert "JAVA_TOOL_OPTIONS=-Xmx2g" in command
    for expected in (
        "--osm-path=/data/in.osm.pbf",
        "--output=/data/region.mbtiles",
        "--bounds=78.2,17.2,78.65,17.6",
        "--maxzoom=14",
        "--download",
    ):
        assert expected in command
    assert cwd == tmp_path


def test_planetiler_jar_runner_needs_a_jar_and_sets_the_heap(tmp_path: Path) -> None:
    with pytest.raises(mod.StepError, match="planetiler-jar"):
        mod.planetiler_command(
            "jar", work=tmp_path, osm=tmp_path / "a", output=tmp_path / "b", bounds=AOI, maxzoom=14, memory_gb=1
        )
    command, _ = mod.planetiler_command(
        "jar", work=tmp_path, osm=tmp_path / "a", output=tmp_path / "b", bounds=AOI, maxzoom=14, memory_gb=3,
        jar=tmp_path / "planetiler.jar",
    )  # fmt: skip
    assert command[:4] == ["java", "-Xmx3g", "-jar", str(tmp_path / "planetiler.jar")]


@pytest.mark.parametrize("maxzoom", [0, 17, -1])
def test_zoom_outside_planetilers_range_is_refused(tmp_path: Path, maxzoom: int) -> None:
    with pytest.raises(mod.StepError):
        mod.planetiler_command(
            "binary", work=tmp_path, osm=tmp_path / "a", output=tmp_path / "b", bounds=AOI, maxzoom=maxzoom, memory_gb=1
        )


def test_osrm_runs_extract_partition_customize_in_that_order(tmp_path: Path) -> None:
    commands = mod.osrm_commands(directory=tmp_path)
    tools = [next(part for part in command if part.startswith("osrm-")) for command in commands]
    assert tools == ["osrm-extract", "osrm-partition", "osrm-customize"]  # MLD: no osrm-contract
    assert "-p" in commands[0]
    assert commands[0][commands[0].index("-p") + 1] == "/opt/car.lua"
    assert all(f"{tmp_path.resolve()}:/data" in command for command in commands)
    assert commands[1][-1] == commands[2][-1] == "/data/region.osrm"


def test_osmium_crop_keeps_complete_ways() -> None:
    command = mod.osmium_command(Path("in.osm.pbf"), Path("out.osm.pbf"), AOI)
    assert command[:2] == ["osmium", "extract"]
    assert command[command.index("--bbox") + 1] == "78.2,17.2,78.65,17.6"
    assert command[command.index("--strategy") + 1] == "complete_ways"


# ------------------------------------------------------------------------------- download and MD5


def test_md5_file_parsing() -> None:
    good = "d41d8cd98f00b204e9800998ecf8427e  southern-zone-latest.osm.pbf\n"
    assert mod.parse_md5_file(good) == "d41d8cd98f00b204e9800998ecf8427e"
    for bad in ("", "not a hash file", "zz1d8cd98f00b204e9800998ecf8427e  x", "d41d8cd9  x"):
        with pytest.raises(mod.StepError):
            mod.parse_md5_file(bad)


def test_md5_of_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(b"abc" * 1000)
    assert mod.md5_of(path) == hashlib.md5(b"abc" * 1000, usedforsecurity=False).hexdigest()


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data, self._at = data, 0

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        chunk, self._at = self._data[self._at : self._at + size], self._at + size
        return chunk


def test_download_is_atomic_and_https_only(tmp_path: Path) -> None:
    target = tmp_path / "x.osm.pbf"
    mod.download("https://example.org/x", target, opener=lambda _u: FakeResponse(b"data"))
    assert target.read_bytes() == b"data"
    assert not target.with_suffix(".pbf.part").exists()
    with pytest.raises(mod.StepError, match="https"):
        mod.download("http://example.org/x", tmp_path / "y")


def run_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *extra: str, md5_text: str | None) -> int:
    monkeypatch.setattr(
        mod,
        "fetch_text",
        lambda _url, timeout=30: (_ for _ in ()).throw(urllib.error.URLError("offline"))
        if md5_text is None
        else md5_text,
    )
    monkeypatch.setattr(mod, "download", lambda _u, target, **_k: target.write_bytes(b"pbf-bytes"))
    return mod.main(["download", "--work-dir", str(tmp_path), *extra])


def test_download_with_matching_md5_records_provenance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    good = hashlib.md5(b"pbf-bytes", usedforsecurity=False).hexdigest()
    assert run_download(monkeypatch, tmp_path, md5_text=f"{good}  southern-zone-latest.osm.pbf\n") == 0
    record = json.loads((tmp_path / "osm-source.json").read_text())
    assert record["md5_verified"] is True
    assert record["md5"] == good
    assert "ODbL" in record["licence"]


def test_download_with_wrong_md5_deletes_the_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_download(monkeypatch, tmp_path, md5_text="0" * 32 + "  x\n") == 1
    assert "MD5 mismatch" in capsys.readouterr().err
    assert not (tmp_path / "southern-zone-latest.osm.pbf").exists()


def test_download_without_a_checkable_md5_needs_an_explicit_opt_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_download(monkeypatch, tmp_path, md5_text=None) == 1
    assert "--md5" in capsys.readouterr().err
    assert run_download(monkeypatch, tmp_path, "--skip-md5", md5_text=None) == 0
    assert json.loads((tmp_path / "osm-source.json").read_text())["md5_verified"] is False


# ----------------------------------------------------------------------------------- tile validator


def test_a_complete_openmaptiles_file_passes(tmp_path: Path) -> None:
    facts = mod.check_mbtiles(make_mbtiles(tmp_path / "a.mbtiles"), AOI)
    assert facts["tiles"] == 3
    assert {"transportation", "place", "water"} <= set(facts["layers"])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"tile_format": "png"}, "format=pbf"),
        ({"tiles": 0}, "no tiles"),
        ({"layers": ("transportation", "place")}, "water"),
        ({"bounds": "10,10,11,11"}, "do not overlap"),
        ({"attribution": "(c) somebody"}, "OpenStreetMap"),
    ],
)
def test_defective_tile_files_are_refused(tmp_path: Path, overrides: dict[str, object], message: str) -> None:
    with pytest.raises(mod.StepError, match=message):
        mod.check_mbtiles(make_mbtiles(tmp_path / "a.mbtiles", **overrides), AOI)  # type: ignore[arg-type]


def test_missing_and_non_sqlite_files_are_refused(tmp_path: Path) -> None:
    with pytest.raises(mod.StepError, match="does not exist"):
        mod.check_mbtiles(tmp_path / "none.mbtiles", AOI)
    junk = tmp_path / "junk.mbtiles"
    junk.write_bytes(b"this is not sqlite" * 50)
    with pytest.raises(mod.StepError, match="not an MBTiles"):
        mod.check_mbtiles(junk, AOI)


def test_pmtiles_step_converts_a_valid_file_and_refuses_an_invalid_one(tmp_path: Path) -> None:
    good = make_mbtiles(tmp_path / "good.mbtiles")
    output = tmp_path / "out" / "region.pmtiles"
    assert mod.main(["pmtiles", str(good), "--output", str(output)]) == 0
    assert output.is_file()
    bad = make_mbtiles(tmp_path / "bad.mbtiles", layers=("transportation",))
    assert mod.main(["pmtiles", str(bad), "--output", str(tmp_path / "bad.pmtiles")]) == 1
    assert not (tmp_path / "bad.pmtiles").exists()


# --------------------------------------------------------------------------------- routing validator


def osrm_answer(distance_m: float, duration_s: float, code: str = "Ok") -> str:
    return json.dumps({"code": code, "routes": [{"distance": distance_m, "duration": duration_s}]})


def test_a_plausible_route_passes() -> None:
    result = mod.check_routing("http://127.0.0.1:5000", fetch=lambda _u: osrm_answer(17_500, 2_100))
    assert result["distance_km"] == 17.5
    assert result["straight_line_km"] > 10


def test_the_request_is_a_lng_lat_driving_route_between_two_points_in_the_region() -> None:
    seen: list[str] = []
    mod.check_routing("http://osrm:5000/", fetch=lambda url: seen.append(url) or osrm_answer(17_500, 2_100))
    assert seen[0].startswith("http://osrm:5000/route/v1/driving/78.4747,17.3616;78.3772,17.4435")


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (osrm_answer(0, 0, code="NoRoute"), "NoRoute"),
        (osrm_answer(5_000, 600), "shorter than the straight line"),
        (osrm_answer(500_000, 30_000), "plausible"),
        (osrm_answer(17_500, 5), "implausible"),
        (json.dumps({"code": "Ok", "routes": []}), "no route"),
        (json.dumps({"code": "Ok", "routes": [{"distance": "far", "duration": "long"}]}), "numeric"),
        ("[]", "did not return a route"),
    ],
)
def test_implausible_or_failed_answers_are_refused(answer: str, message: str) -> None:
    with pytest.raises(mod.StepError, match=message):
        mod.check_routing("http://127.0.0.1:5000", fetch=lambda _u: answer)


def test_unreachable_or_malformed_routing_urls_are_reported() -> None:
    def refuse(_url: str) -> str:
        raise urllib.error.URLError("connection refused")

    with pytest.raises(mod.StepError, match="could not get a route"):
        mod.check_routing("http://127.0.0.1:5000", fetch=refuse)
    with pytest.raises(mod.StepError, match="--url"):
        mod.check_routing("ftp://x")
    with pytest.raises(mod.StepError, match="could not get a route"):
        mod.check_routing("http://127.0.0.1:5000", fetch=lambda _u: "<html>not json</html>")


# ------------------------------------------------------------------------------------- command line


def test_dry_run_prints_every_command_and_creates_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    work, osrm = tmp_path / "work", tmp_path / "osrm"
    for step in (["download"], ["tiles"], ["pmtiles"], ["crop"], ["routing", "--osrm-dir", str(osrm)]):
        assert mod.main([*step, "--work-dir", str(work), "--dry-run"]) == 0
    out = capsys.readouterr().out
    for fragment in ("docker run", "planetiler", "--bounds=78.2,17.2,78.65,17.6", "osmium extract", "osrm-extract",
                     "osrm-partition", "osrm-customize", "mbtiles_to_pmtiles.py"):  # fmt: skip
        assert fragment in out
    assert not work.exists()
    assert not osrm.exists()


def test_steps_report_a_missing_input_instead_of_a_traceback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for step in (["tiles"], ["crop"], ["routing", "--osrm-dir", str(tmp_path / "o")]):
        assert mod.main([*step, "--work-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert err.count("not found") == 3
    assert "Traceback" not in err


def test_a_missing_tool_is_named(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod.shutil, "which", lambda _name: None)
    (tmp_path / "southern-zone-latest.osm.pbf").write_bytes(b"x")
    assert mod.main(["crop", "--work-dir", str(tmp_path)]) == 1
    assert "`osmium` is not installed" in capsys.readouterr().err


def test_a_failing_tool_stops_the_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Done:
        returncode = 3

    monkeypatch.setattr(mod.shutil, "which", lambda _name: "/usr/bin/true")
    monkeypatch.setattr(mod.subprocess, "run", lambda *_a, **_k: Done())
    with pytest.raises(mod.StepError, match="status 3"):
        mod.run(["osmium", "x"], cwd=None, dry_run=False)
