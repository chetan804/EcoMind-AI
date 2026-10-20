"""The offline-map preparation script: argument validation and the command it would run."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "maps" / "prepare_offline_maps.py"
spec = importlib.util.spec_from_file_location("prepare_offline_maps", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_bbox_is_parsed_and_validated() -> None:
    assert module.parse_bbox("78.2,17.2,78.7,17.6") == (78.2, 17.2, 78.7, 17.6)
    for bad in ["1,2,3", "a,b,c,d", "10,0,5,1", "0,10,1,5", "-200,0,1,1", "0,-95,1,1"]:
        with pytest.raises(module.UsageError):
            module.parse_bbox(bad)


def test_extract_command_is_a_plain_argv_without_shell_strings() -> None:
    command = module.extract_command(
        "pmtiles", "https://example.org/x.pmtiles", Path("out.pmtiles"), (78.2, 17.2, 78.7, 17.6), 14
    )
    assert command == [
        "pmtiles",
        "extract",
        "https://example.org/x.pmtiles",
        "out.pmtiles",
        "--bbox=78.2,17.2,78.7,17.6",
        "--maxzoom=14",
    ]
    with pytest.raises(module.UsageError):
        module.extract_command("pmtiles", "s", Path("o"), (0, 0, 1, 1), 16)


def test_dry_run_prints_and_runs_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    code = module.main(["tiles", "--bbox", "78.2,17.2,78.7,17.6", "--source", "x.pmtiles", "--dry-run"])
    assert code == 0
    assert "--bbox=78.2,17.2,78.7,17.6" in capsys.readouterr().out


def test_bad_arguments_exit_with_a_message_not_a_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    assert module.main(["tiles", "--bbox", "oops", "--source", "x", "--dry-run"]) == 2
    assert "--bbox" in capsys.readouterr().err


def test_only_the_default_latin_ranges_are_copied_unless_all_are_requested() -> None:
    latin = "basemaps-assets-main/fonts/Noto Sans Regular/256-511.pbf"
    other = "basemaps-assets-main/fonts/Noto Sans Regular/2304-2559.pbf"
    assert module.wanted_member(latin, False) == "fonts/Noto Sans Regular/256-511.pbf"
    assert module.wanted_member(other, False) is None
    assert module.wanted_member(other, True) == "fonts/Noto Sans Regular/2304-2559.pbf"
    assert module.wanted_member("basemaps-assets-main/fonts/Other Font/0-255.pbf", True) is None
    assert module.wanted_member("basemaps-assets-main/sprites/v4/light.png", True) is None
