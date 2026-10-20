from __future__ import annotations

import datetime as dt
import decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.common.enums import QuantityUnit
from app.modules.forecasting.constants import ForecastGranularity

DataKind = Literal["platform", "public_reference"]


class Provenance(BaseModel):
    source_url: str
    source_commit: str
    licence_note: str
    processing_note: str


class SeriesInfo(BaseModel):
    ref: str = Field(description="`platform:collected_weight_kg` or `reference:<key>`")
    name: str
    data_kind: DataKind
    label: str = Field(description="Wording the UI must show next to the series")
    unit: QuantityUnit
    granularity: ForecastGranularity
    points: int
    first_period: dt.date | None
    last_period: dt.date | None
    interpolated_points: int
    provenance: Provenance | None = None


class SeriesPointOut(BaseModel):
    period_start: dt.date
    value: float
    interpolated: bool


class SeriesHistory(BaseModel):
    series: SeriesInfo
    points: list[SeriesPointOut]


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: str = Field(min_length=3, max_length=80)
    horizon_weeks: int = Field(default=4, ge=1, le=12)
    save: bool = Field(default=True, description="Persist the forecast rows")


class ForecastPoint(BaseModel):
    period_start: dt.date
    period_end: dt.date
    predicted: decimal.Decimal
    lower: decimal.Decimal
    upper: decimal.Decimal


class BacktestEvidence(BaseModel):
    """How the chosen model did on the most recent history (rolling origin, no look-ahead)."""

    horizon_weeks: int
    origins: int
    candidate_mae: dict[str, float]
    selected_mae: float | None
    naive_mae: float | None
    mae_vs_naive: float | None = Field(description="selected MAE / naive MAE; < 1 is better")
    beats_naive: bool | None


class ModelInfo(BaseModel):
    name: str
    engine_version: str
    parameters: dict[str, float]
    selection: str


class ForecastOut(BaseModel):
    series: SeriesInfo
    model: ModelInfo
    backtest: BacktestEvidence
    interval_level: float
    points: list[ForecastPoint]
    caveats: list[str]
    generated_at: dt.datetime
    saved: bool


class StoredForecastOut(BaseModel):
    series: SeriesInfo
    generated_at: dt.datetime | None
    model_name: str | None
    model_version: str | None
    points: list[ForecastPoint]
