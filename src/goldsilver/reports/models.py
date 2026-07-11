"""Data types for the report engine: enums, the ticker value object, run + verdict records."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from goldsilver.reports.constants import (
    METAL_LABELS,
    PINNED_COMMODITIES,
    PINNED_METALS,
    safe_name,
)


class ReportStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    MALFORMED = "MALFORMED"
    TIMEOUT = "TIMEOUT"
    CLI_MISSING = "CLI_MISSING"
    ERROR = "ERROR"


class SwedishPhase(str, Enum):
    MORNING_STRENGTH = "MORNING_STRENGTH"
    MIDDAY_WEAKNESS = "MIDDAY_WEAKNESS"
    TREND_FOLLOWING = "TREND_FOLLOWING"
    US_INFLUENCE = "US_INFLUENCE"
    US_DOMINATED = "US_DOMINATED"
    CLOSED = "CLOSED"


class USMarketState(str, Enum):
    CLOSED = "CLOSED"
    PRE_MARKET = "PRE_MARKET"
    OPENING = "OPENING"
    OPEN = "OPEN"
    NEAR_CLOSE = "NEAR_CLOSE"


TickerKind = Literal["metal", "commodity", "stock"]
Impact = Literal["Positive", "Neutral", "Negative"]
Call = Literal["BUY", "HOLD", "SELL"]


class ReportTicker:
    """One instrument to analyze. Metals are pinned and non-removable."""

    __slots__ = ("symbol", "label", "pinned", "kind")

    def __init__(
        self,
        symbol: str,
        label: str,
        *,
        pinned: bool = False,
        kind: TickerKind = "stock",
    ) -> None:
        self.symbol = symbol
        self.label = label
        self.pinned = pinned
        self.kind = kind

    @property
    def safe_name(self) -> str:
        return safe_name(self.symbol)

    @classmethod
    def metal(cls, symbol: str) -> "ReportTicker":
        return cls(symbol, METAL_LABELS.get(symbol, symbol), pinned=True, kind="metal")

    @classmethod
    def commodity(cls, symbol: str) -> "ReportTicker":
        return cls(
            symbol, METAL_LABELS.get(symbol, symbol), pinned=True, kind="commodity"
        )

    @classmethod
    def stock(cls, symbol: str) -> "ReportTicker":
        return cls(symbol, symbol, pinned=False, kind="stock")

    def __repr__(self) -> str:
        return (
            f"ReportTicker({self.symbol!r}, pinned={self.pinned}, kind={self.kind!r})"
        )


def pinned_metal_tickers() -> list[ReportTicker]:
    return [ReportTicker.metal(sym) for sym in PINNED_METALS]


def pinned_commodity_tickers() -> list[ReportTicker]:
    return [ReportTicker.commodity(sym) for sym in PINNED_COMMODITIES]


class Verdict(BaseModel):
    """Structured recommendation, parsed from the report's line-1 VERDICT comment."""

    intraday: Call
    swing: Call
    confidence: int = Field(ge=0, le=100)
    swedish_phase: str
    us_state: str
    usd_impact: Impact
    gold_impact: Impact
    news_impact: Impact
    geopolitical_impact: Impact
    top_reasons: list[str]
    what_would_change: list[str]


class ReportRun(BaseModel):
    """One execution record, serialized to the sidecar JSON next to each report."""

    ticker: str
    label: str
    kind: TickerKind
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    status: ReportStatus = ReportStatus.PENDING
    html_path: str | None = None
    verdict: Verdict | None = None
    error: str | None = None
