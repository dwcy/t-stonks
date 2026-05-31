from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


CalendarSource = Literal["FED", "ECB", "RIKSBANK"]
EventImportance = Literal["HIGH", "MED", "LOW"]
EventStatus = Literal["SCHEDULED", "RELEASED", "CANCELLED", "PASSED"]
SnapshotStatus = Literal["ok", "stale", "unavailable"]
FxPair = Literal["USDSEK", "CADSEK"]
CommoditySymbol = Literal["BRENT"]


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
    status: EventStatus = "SCHEDULED"

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


NewsSource = Literal[
    "REUTERS", "CNBC", "WllStrtJrnl", "BLOOMBERG", "POLITICO", "YAHOO", "FOX",
    "DgnsIndstr", "SVT", "BREAKIT", "AffrsVrldn",
    "REDEYE", "BrsKlln", "Placera", "EFN", "TRUMP",
]


class NewsItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: NewsSource
    title: str
    url: str
    published: datetime

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
