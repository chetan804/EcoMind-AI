"""The load-test script: every endpoint it calls exists (GET) in the real API, and its guards work."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from app.core.config import Settings
from app.main import create_app

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "perf" / "load_test.py"
spec = importlib.util.spec_from_file_location("load_test", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture(scope="module")
def openapi() -> dict[str, Any]:
    return create_app(Settings(_env_file=None)).openapi()  # type: ignore[call-arg]


def test_every_endpoint_in_the_scenario_is_a_real_get_route(openapi: dict[str, Any]) -> None:
    missing = [
        path
        for path, _, _ in module.ENDPOINTS
        if "get" not in openapi["paths"].get(path.split("?")[0], {})
    ]
    assert missing == []


def test_the_scenario_never_writes() -> None:
    assert all(not path.startswith("/api/v1/auth") for path, _, _ in module.ENDPOINTS)


def test_percentiles() -> None:
    values = [float(n) for n in range(1, 101)]
    assert module.percentile(values, 0.5) in (50.0, 51.0)
    assert module.percentile(values, 0.95) in (95.0, 96.0)
    assert module.percentile(values, 1.0) == 100.0
    assert module.percentile([], 0.5) != module.percentile([], 0.5)  # NaN, not a made-up number


def test_a_non_local_target_is_refused_unless_explicitly_allowed() -> None:
    with pytest.raises(SystemExit, match="not local"):
        module.main(["--base-url", "https://example.org"])
