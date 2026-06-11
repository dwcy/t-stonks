from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import yfinance as yf
from pydantic import ValidationError

from goldsilver.data.models_macro import StockQuote
from goldsilver.data.stock_presets import PRESET_NAMES


StockHandler = Callable[[list[StockQuote]], Awaitable[None] | None]
StockStaleHandler = Callable[[datetime], Awaitable[None] | None]

STOCK_REFRESH_INTERVAL_S = 60.0
MAX_SPARK_POINTS = 60


class StockService:
    def __init__(
        self,
        tickers: list[str],
        handler: StockHandler | None = None,
        stale_handler: StockStaleHandler | None = None,
        *,
        refresh_interval_s: float = STOCK_REFRESH_INTERVAL_S,
    ) -> None:
        self._tickers = list(tickers)
        self._handler = handler
        self._stale_handler = stale_handler
        self._refresh_interval_s = refresh_interval_s
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def set_tickers(self, tickers: list[str]) -> None:
        self._tickers = list(tickers)

    def start(self) -> None:
        if not self._tickers:
            return
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="stock-loop")

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
        if self._tickers:
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
        quotes = await asyncio.to_thread(_fetch_batch, list(self._tickers))
        if not quotes:
            await self._emit_stale()
            return
        await self._emit(quotes)

    async def _emit(self, quotes: list[StockQuote]) -> None:
        if self._handler is None:
            return
        result = self._handler(quotes)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_stale(self) -> None:
        if self._stale_handler is None:
            return
        result = self._stale_handler(datetime.now(timezone.utc))
        if asyncio.iscoroutine(result):
            await result


_NAME_CACHE: dict[str, str] = {}


def _resolve_display_name(sym: str, ticker: yf.Ticker | None) -> str:
    cached = _NAME_CACHE.get(sym)
    if cached:
        return cached
    name = PRESET_NAMES.get(sym.upper())
    if not name and ticker is not None:
        try:
            raw = ticker.info.get("shortName") or ticker.info.get("longName")
            if isinstance(raw, str) and raw.strip():
                name = raw.strip()
        except Exception:
            name = None
    name = name or sym
    _NAME_CACHE[sym] = name
    return name


def _fetch_batch(tickers: list[str]) -> list[StockQuote]:
    out: list[StockQuote] = []
    for sym in tickers:
        quote = fetch_single_quote(sym)
        if quote is not None:
            out.append(quote)
    return out


def fetch_single_quote(sym: str) -> StockQuote | None:
    try:
        ticker = yf.Ticker(sym)
        intraday = ticker.history(period="5d", interval="5m")
    except Exception:
        return None
    if intraday is None or len(intraday) == 0:
        return None
    try:
        closes = [float(c) for c in intraday["Close"].tolist() if c == c]
    except Exception:
        return None
    if not closes:
        return None

    timestamps = [t.to_pydatetime() for t in intraday.index]
    latest_ts = timestamps[-1]
    if latest_ts.tzinfo is None:
        latest_ts = latest_ts.replace(tzinfo=timezone.utc)

    latest_date = latest_ts.date()
    today_closes: list[float] = []
    prior_close = closes[0]
    for ts, close in zip(timestamps, closes):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts.date() == latest_date:
            today_closes.append(close)
        else:
            prior_close = close

    price = closes[-1]
    fast_price: float | None = None
    fast_prev: float | None = None
    currency = "USD"
    try:
        fast_info = ticker.fast_info  # type: ignore[attr-defined]
        last_price = fast_info.last_price
        if (
            isinstance(last_price, (int, float))
            and last_price == last_price
            and last_price > 0
        ):
            fast_price = float(last_price)
        prev = fast_info.previous_close
        if isinstance(prev, (int, float)) and prev == prev and prev > 0:
            fast_prev = float(prev)
        info_currency = fast_info.currency
        if isinstance(info_currency, str) and info_currency.strip():
            currency = info_currency.strip().upper()
    except Exception:
        pass

    if fast_price is not None:
        price = fast_price
    previous_close = (
        fast_prev
        if fast_prev is not None
        else (prior_close if prior_close > 0 else price)
    )

    if not today_closes:
        today_closes = [price]
    elif price != today_closes[-1]:
        today_closes.append(price)
    if len(today_closes) > MAX_SPARK_POINTS:
        today_closes = today_closes[-MAX_SPARK_POINTS:]

    try:
        return StockQuote(
            ticker=sym,
            display_name=_resolve_display_name(sym, ticker),
            price=price,
            previous_close=previous_close,
            intraday_closes=tuple(today_closes),
            currency=currency,
            time=latest_ts.astimezone(timezone.utc),
        )
    except ValidationError:
        return None
