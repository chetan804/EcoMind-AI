"""Adapter to the pure-numpy forecasting algorithms in ``ml/time_series/algorithms.py``.

The backend does not import the ``ml`` package statically (it is an isolated capability, and
the algorithms are developed and benchmarked there). They are loaded by name at call time; when
the package is not installed alongside the backend the endpoints answer ``503
forecast_engine_unavailable`` instead of inventing numbers.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from app.core.exceptions import AppError

ENGINE_VERSION = "ts-1.0.0"
MODULE = "ml.time_series.algorithms"


class ForecastEngineUnavailableError(AppError):
    status_code = 503
    code = "forecast_engine_unavailable"


def algorithms() -> ModuleType:
    try:
        return importlib.import_module(MODULE)
    except ModuleNotFoundError as exc:
        raise ForecastEngineUnavailableError(
            "The forecasting algorithms are not installed on this server"
        ) from exc
