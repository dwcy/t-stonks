"""Generic market data models: spot Tick and OHLCV Bar."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Tick(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    price: float
    time: datetime
    change: float
    change_percent: float
    day_high: float
    day_low: float
    prev_close: float


class Bar(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class DailyChange(BaseModel):
    """One trading day's summary, derived from a Bar series for the 40-day strip."""

    model_config = ConfigDict(frozen=True)

    date: date
    close: float
    change_percent: float
    direction: Literal["up", "down", "flat"]
