# > 400 LoC justified: one cohesive Pydantic registry for the shared macro data layer
"""Macro & market data models (FX, commodities, stocks, news, calendar, social)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


CalendarSource = Literal["FED", "ECB", "RIKSBANK"]
EventImportance = Literal["HIGH", "MED", "LOW"]
EventStatus = Literal["SCHEDULED", "RELEASED", "CANCELLED", "PASSED"]
SnapshotStatus = Literal["ok", "stale", "unavailable"]
FxPair = Literal["USDSEK", "CADSEK", "EURSEK"]
CommoditySymbol = Literal["BRENT", "COPPER", "BTC", "DXY"]
ImpactDirection = Literal["bullish", "bearish", "neutral"]
SurpriseDirection = Literal["above", "below", "inline", "na"]


class RealYieldPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: float
    previous: float | None
    asof: date


RateSource = Literal["fed", "riksbank"]


class RatePoint(BaseModel):
    """A central bank's current policy rate (USA Fed funds / Sweden Riksbank)."""

    model_config = ConfigDict(frozen=True)

    value: float
    previous: float | None
    asof: date
    source: RateSource


class EventAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    surprise: SurpriseDirection = "na"
    gold: ImpactDirection = "neutral"
    silver: ImpactDirection = "neutral"
    usd: ImpactDirection = "neutral"
    rationale: str = ""


class CalendarEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: CalendarSource
    title: str
    scheduled_time: datetime
    all_day: bool = False
    importance: EventImportance | None = None
    forecast: str | None = None
    previous: str | None = None
    actual: str | None = None
    actual_summary: str | None = None
    status: EventStatus = "SCHEDULED"
    analysis: EventAnalysis | None = None

    @field_validator("scheduled_time")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("scheduled_time must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("title")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title must be non-empty")
        return stripped


class CalendarDay(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    bucket: Literal["yesterday", "today", "upcoming"]
    events: tuple[CalendarEvent, ...] = ()


class CalendarSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    days: tuple[CalendarDay, ...]
    fetched_at: datetime
    status: SnapshotStatus = "ok"


class OmxDay(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    close: float
    change_percent: float


class OmxSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    days: tuple[OmxDay, ...]
    current_price: float
    current_change_percent: float
    fetched_at: datetime
    market_open: bool
    latest_session_date: date | None = None
    latest_session_close_time: datetime | None = None
    ytd_change_percent: float | None = None

    @field_validator("fetched_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        return v.astimezone(timezone.utc)


class FxRate(BaseModel):
    model_config = ConfigDict(frozen=True)

    pair: FxPair
    rate: float
    previous_close: float
    time: datetime

    @field_validator("rate", "previous_close")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v < 1.0:
            raise ValueError(f"FX rate below 1.0 SEK — likely misparsed: {v}")
        return v

    @property
    def change(self) -> float:
        return self.rate - self.previous_close

    @property
    def change_percent(self) -> float:
        if self.previous_close == 0.0:
            return 0.0
        return (self.rate - self.previous_close) / self.previous_close * 100.0


SignalKind = Literal["momentum", "recoil"]
SignalAction = Literal["BUY", "SELL", "NONE"]


class Signal(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    strategy: str
    kind: SignalKind
    action: SignalAction
    intensity_sigma: float
    reason: str
    at: datetime

    @field_validator("at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("at must be timezone-aware")
        return v.astimezone(timezone.utc)


# A news source is an app-defined label, not a fixed registry — apps (goldsilver,
# quantum, …) supply their own, so this stays an open string rather than a Literal.
NewsSource = str

# "confirmed" only when a real <pubDate>/ISO date parsed successfully; every fallback
# path (URL-date stagger, feed build time, fetch time) is "approximate" — the UI must
# not present a guessed timestamp with the same confidence as a real one.
NewsTimeConfidence = Literal["confirmed", "approximate"]


class NewsItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: NewsSource
    title: str
    url: str
    published: datetime
    time_confidence: NewsTimeConfidence = "confirmed"

    @field_validator("published")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("published must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("title", "url")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must be non-empty")
        return stripped


class CommodityQuote(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: CommoditySymbol
    price: float
    previous_close: float
    time: datetime

    @field_validator("price", "previous_close")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v <= 0.0:
            raise ValueError(f"commodity price must be positive: {v}")
        return v

    @property
    def change(self) -> float:
        return self.price - self.previous_close

    @property
    def change_percent(self) -> float:
        if self.previous_close == 0.0:
            return 0.0
        return (self.price - self.previous_close) / self.previous_close * 100.0


Party = Literal["R", "D", "I"]
TradeSide = Literal["BUY", "SELL", "EXCHANGE"]
Chamber = Literal["HOUSE", "SENATE"]


class CongressTrade(BaseModel):
    model_config = ConfigDict(frozen=True)

    politician: str
    party: Party
    chamber: Chamber
    ticker: str
    asset_name: str = ""
    side: TradeSide
    size_bucket: str
    traded_at: datetime
    filed_at: datetime | None = None

    @field_validator("traded_at")
    @classmethod
    def _traded_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("traded_at must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("filed_at")
    @classmethod
    def _filed_tz(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            raise ValueError("filed_at must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("politician", "ticker", "size_bucket")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must be non-empty")
        return stripped


InsiderSide = Literal["BUY", "SELL", "OTHER"]
Sentiment = Literal["BULL", "BEAR"]


class StockTwitMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    user_username: str
    user_followers: int = 0
    body: str
    sentiment: Sentiment | None = None
    tickers: tuple[str, ...] = ()
    created_at: datetime
    source_ticker: str

    @field_validator("created_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("user_username", "body", "source_ticker")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must be non-empty")
        return stripped


class InsiderTrade(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer_ticker: str
    issuer_name: str
    insider_name: str
    insider_role: str
    transaction_date: datetime
    code: str
    side: InsiderSide
    shares: float | None = None
    price_per_share: float | None = None
    value_usd: float | None = None
    accession: str

    @field_validator("transaction_date")
    @classmethod
    def _tx_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("transaction_date must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("issuer_ticker", "insider_name", "accession", "code")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must be non-empty")
        return stripped


class PoliticianStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    politician: str
    party: Party
    chamber: Chamber
    trade_count: int
    buy_count: int
    avg_return_pct: float | None
    win_rate_pct: float | None
    last_trade_at: datetime

    @field_validator("last_trade_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("last_trade_at must be timezone-aware")
        return v.astimezone(timezone.utc)


class StockQuote(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str
    display_name: str
    price: float
    previous_close: float
    intraday_closes: tuple[float, ...] = ()
    currency: str = "USD"
    time: datetime

    @field_validator("price", "previous_close")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v <= 0.0:
            raise ValueError(f"stock price must be positive: {v}")
        return v

    @field_validator("ticker", "display_name")
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
