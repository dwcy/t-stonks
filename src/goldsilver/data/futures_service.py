"""Poll yfinance for pre-open index futures (US live) plus EU cash-index proxies."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import yfinance as yf
from pydantic import ValidationError

from goldsilver.data.models_futures import (
    FuturesKind,
    FuturesMarket,
    FuturesSnapshot,
    FutureQuote,
)

FuturesHandler = Callable[[FuturesSnapshot], Awaitable[None] | None]

FUTURES_REFRESH_INTERVAL_S = 60.0

# (yfinance symbol, label, market, kind, is_live). US =F contracts trade ~23h so
# they carry a genuine pre-open signal; EU cash indices stand still until their
# session opens, so they ride as labeled, non-live proxies (Avanza has no futures).
_REGISTRY: tuple[tuple[str, str, FuturesMarket, FuturesKind, bool], ...] = (
    ("ES=F", "S&P", "US", "index_future", True),
    ("NQ=F", "Nasdaq", "US", "index_future", True),
    ("YM=F", "Dow", "US", "index_future", True),
    ("RTY=F", "Russell", "US", "index_future", True),
    ("GC=F", "Guld", "US", "commodity", True),
    ("SI=F", "Silver", "US", "commodity", True),
    ("^VIX", "VIX", "US", "vol", True),
    ("^TNX", "US10Y", "US", "rate", True),
    ("^OMX", "OMXS30", "SE", "cash_index", False),
    ("^GDAXI", "DAX", "EU", "cash_index", False),
    ("^STOXX50E", "EStoxx50", "EU", "cash_index", False),
)


class FuturesService:
    def __init__(
        self,
        handler: FuturesHandler | None = None,
        *,
        refresh_interval_s: float = FUTURES_REFRESH_INTERVAL_S,
    ) -> None:
        self._handler = handler
        self._refresh_interval_s = refresh_interval_s
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="futures-loop")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def refresh_now(self) -> None:
        await self._refresh_once()

    async def _run(self) -> None:
        await self._refresh_once()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self._refresh_interval_s
                )
                return
            except asyncio.TimeoutError:
                pass
            await self._refresh_once()

    async def _refresh_once(self) -> None:
        quotes = await asyncio.to_thread(self._fetch_all)
        snapshot = FuturesSnapshot(
            quotes=tuple(quotes),
            fetched_at=datetime.now(timezone.utc),
            status="ok" if quotes else "unavailable",
        )
        await self._emit(snapshot)

    def _fetch_all(self) -> list[FutureQuote]:
        quotes: list[FutureQuote] = []
        for symbol, label, market, kind, is_live in _REGISTRY:
            quote = self._fetch_one(symbol, label, market, kind, is_live)
            if quote is not None:
                quotes.append(quote)
        return quotes

    @staticmethod
    def _fetch_one(
        symbol: str,
        label: str,
        market: FuturesMarket,
        kind: FuturesKind,
        is_live: bool,
    ) -> FutureQuote | None:
        try:
            df = yf.Ticker(symbol).history(period="5d", interval="1d")
        except Exception:
            return None
        if df is None or len(df) < 2:
            return None
        closes = [float(c) for c in df["Close"].tolist() if c == c]
        if len(closes) < 2:
            return None
        last_ts = df.index[-1].to_pydatetime()
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        try:
            return FutureQuote(
                symbol=symbol,
                label=label,
                market=market,
                kind=kind,
                price=closes[-1],
                previous_close=closes[-2],
                is_live=is_live,
                time=last_ts.astimezone(timezone.utc),
            )
        except ValidationError:
            return None

    async def _emit(self, snapshot: FuturesSnapshot) -> None:
        if self._handler is None:
            return
        result = self._handler(snapshot)
        if asyncio.iscoroutine(result):
            await result
