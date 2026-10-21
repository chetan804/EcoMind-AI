"""MBTiles -> PMTiles conversion: layout detection, metadata expansion and refusal of bad input.

The tile bytes are opaque to the converter, so these tests use small stand-in payloads; the real
style is exercised against real vector tiles by the frontend and the end-to-end screenshots.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "maps" / "mbtiles_to_pmtiles.py"
spec = importlib.util.spec_from_file_location("mbtiles_to_pmtiles", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

OPENMAPTILES = ["transportation", "place", "water", "landuse"]


def make_mbtiles(
    path: Path,
    *,
    layers: list[str] | None = None,
    tile_format: str = "pbf",
    zooms: tuple[int, ...] = (0, 1, 2),
    compressed: bool = False,
) -> Path:
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE metadata (name TEXT, value TEXT);"
        "CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB);"
    )
    metadata = {
        "name": "Test",
        "format": tile_format,
        "minzoom": str(min(zooms)),
        "maxzoom": str(max(zooms)),
        "bounds": "78.2,17.2,78.65,17.6",
        "attribution": "© MapTiler © OpenStreetMap contributors",
        "json": json.dumps({"vector_layers": [{"id": name} for name in layers or OPENMAPTILES]}),
    }
    connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
    for z in zooms:
        payload = f"tile-{z}".encode()
        connection.execute(
            "INSERT INTO tiles VALUES (?, 0, 0, ?)", (z, gzip.compress(payload) if compressed else payload)
        )
    connection.commit()
    connection.close()
    return path


@pytest.mark.parametrize("compressed", [False, True])
def test_converts_and_reads_back_with_vector_layers_at_the_top_level(
    tmp_path: Path, compressed: bool
) -> None:
    source = make_mbtiles(tmp_path / "a.mbtiles", compressed=compressed)
    output = tmp_path / "out" / "region.pmtiles"
    assert module.main([str(source), "--output", str(output)]) == 0
    count, metadata = module.verify(output)
    assert count == 3
    assert module.layer_ids(metadata) == OPENMAPTILES
    assert module.schema_of(metadata) == "openmaptiles"
    assert metadata["attribution"] == "© MapTiler © OpenStreetMap contributors"
    assert not output.with_suffix(".pmtiles.part").exists()


def test_tiles_are_stored_gzip_compressed_and_addressable(tmp_path: Path) -> None:
    from pmtiles.reader import MmapSource, Reader

    source = make_mbtiles(tmp_path / "a.mbtiles", zooms=(0, 1))
    output = tmp_path / "r.pmtiles"
    assert module.main([str(source), "--output", str(output)]) == 0
    with output.open("rb") as handle:
        reader = Reader(MmapSource(handle))
        data = reader.get(0, 0, 0)
    assert data is not None
    assert gzip.decompress(data) == b"tile-0"


def test_maxzoom_drops_higher_tiles_and_is_recorded(tmp_path: Path) -> None:
    source = make_mbtiles(tmp_path / "a.mbtiles", zooms=(0, 1, 2, 3))
    output = tmp_path / "r.pmtiles"
    assert module.main([str(source), "--output", str(output), "--maxzoom", "1"]) == 0
    count, metadata = module.verify(output)
    assert count == 2
    assert metadata["maxzoom"] == "1"


def test_protomaps_and_unknown_layouts_are_told_apart() -> None:
    assert module.schema_of({"vector_layers": [{"id": "earth"}, {"id": "roads"}]}) == "protomaps"
    assert module.schema_of({"vector_layers": [{"id": "poi"}]}) == "unknown"
    assert module.schema_of({}) == "unknown"


def test_refuses_raster_tiles(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_mbtiles(tmp_path / "a.mbtiles", tile_format="png")
    assert module.main([str(source), "--output", str(tmp_path / "r.pmtiles")]) == 1
    assert "only vector tiles" in capsys.readouterr().err
    assert not (tmp_path / "r.pmtiles").exists()


def test_refuses_a_file_that_is_not_mbtiles(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bogus = tmp_path / "x.mbtiles"
    bogus.write_text("not a database")
    assert module.main([str(bogus), "--output", str(tmp_path / "r.pmtiles")]) == 1
    assert "not an MBTiles file" in capsys.readouterr().err


def test_never_overwrites_without_force(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_mbtiles(tmp_path / "a.mbtiles")
    output = tmp_path / "r.pmtiles"
    output.write_bytes(b"precious")
    assert module.main([str(source), "--output", str(output)]) == 1
    assert output.read_bytes() == b"precious"
    assert module.main([str(source), "--output", str(output), "--force"]) == 0
    assert "exists" in capsys.readouterr().err
