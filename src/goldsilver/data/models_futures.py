"""Pydantic models for the pre-open index-futures strip (US live + EU cash proxies)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

FuturesMarket = Literal["US", "SE", "EU"]
FuturesKind = Literal["index_future", "commodity", "rate", "vol", "cash_index"]
FuturesStatus = Literal["ok", "stale", "unavailable"]


class FutureQuote(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    label: str
    market: FuturesMarket
    kind: FuturesKind
    price: float
    previous_close: float
    is_live: bool = True
    source: str = "yfinance"
    time: datetime

    @field_validator("price", "previous_close")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v <= 0.0:
            raise ValueError(f"futures price must be positive: {v}")
        return v

    @field_validator("symbol", "label")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must be non-empty")
        return stripped

    @field_validator("time")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("time must be timezone-aware")
        return v.astimezone(timezone.utc)

    @property
    def change(self) -> float:
        return self.price - self.previous_close

    @property
    def change_percent(self) -> float:
        if self.previous_close == 0.0:
            return 0.0
        return (self.price - self.previous_close) / self.previous_close * 100.0


class FuturesSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    quotes: tuple[FutureQuote, ...]
    fetched_at: datetime
    status: FuturesStatus = "ok"

    @field_validator("fetched_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        return v.astimezone(timezone.utc)
