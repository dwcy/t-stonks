"""StockService — polls yfinance for a list of tickers, emits StockQuote batches."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import yfinance as yf
from pydantic import ValidationError

from marketcore.models import Bar
from marketcore.models_macro import DividendInfo, StockQuote
from marketcore.services.base import PollingService

StockHandler = Callable[[list[StockQuote]], Awaitable[None] | None]
StockStaleHandler = Callable[[datetime], Awaitable[None] | None]

STOCK_REFRESH_INTERVAL_S = 60.0
MAX_SPARK_POINTS = 60

# Apps register display-name overrides (ticker upper-case -> name); empty by default
# so the service stays symbol-agnostic and falls back to yfinance shortName.
NAME_OVERRIDES: dict[str, str] = {}


def register_names(mapping: dict[str, str]) -> None:
    NAME_OVERRIDES.update({k.upper(): v for k, v in mapping.items()})


class StockService(PollingService[list[StockQuote]]):
    def __init__(
        self,
        tickers: list[str],
        handler: StockHandler | None = None,
        stale_handler: StockStaleHandler | None = None,
        *,
        refresh_interval_s: float = STOCK_REFRESH_INTERVAL_S,
    ) -> None:
        super().__init__(handler, stale_handler, refresh_interval_s, "stock-loop")
        self._tickers = list(tickers)

    def set_tickers(self, tickers: list[str]) -> None:
        self._tickers = list(tickers)

    def _should_start(self) -> bool:
        return bool(self._tickers)

    async def refresh_now(self) -> None:
        if self._tickers:
            await self._refresh_once()

    async def _refresh_once(self) -> None:
        quotes = await asyncio.to_thread(_fetch_batch, list(self._tickers))
        if not quotes:
            await self._emit_stale()
            return
        await self._emit(quotes)


_NAME_CACHE: dict[str, str] = {}


def _resolve_display_name(sym: str, ticker: yf.Ticker | None) -> str:
    cached = _NAME_CACHE.get(sym)
    if cached:
        return cached
    key = sym.upper()
    name = NAME_OVERRIDES.get(key)
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
    daily_fallback = False
    try:
        ticker = yf.Ticker(sym)
        intraday = ticker.history(period="5d", interval="5m")
        if intraday is None or len(intraday) == 0:
            # Illiquid names (e.g. TSX Venture .V) have no 5m bars; fall back to daily.
            intraday = ticker.history(period="1mo", interval="1d")
            daily_fallback = True
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

    if daily_fallback:
        prior_close = closes[-2] if len(closes) >= 2 else closes[0]
        today_closes = list(closes)
    else:
        latest_date = latest_ts.date()
        today_closes = []
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


def fetch_daily_history(sym: str, *, period: str = "3mo") -> list[Bar]:
    """Daily OHLCV bars for the chart-detail modal (Story 9) — one-shot, not polled."""
    try:
        df = yf.Ticker(sym).history(period=period, interval="1d")
    except Exception:
        return []
    if df is None or len(df) == 0:
        return []
    bars: list[Bar] = []
    for ts, row in df.iterrows():
        t = ts.to_pydatetime()
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        try:
            bars.append(
                Bar(
                    symbol=sym,
                    time=t.astimezone(timezone.utc),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )
        except (ValueError, KeyError, ValidationError):
            continue
    return bars


def fetch_dividend_info(sym: str) -> DividendInfo:
    """Most recent dividend payment for `sym`, if any — historical only, no
    forward-looking source (yfinance's forward calendar is unreliable across
    tickers, so this deliberately doesn't attempt to parse it)."""
    try:
        series = yf.Ticker(sym).dividends
    except Exception:
        series = None
    if series is None or len(series) == 0:
        return DividendInfo(ticker=sym)
    try:
        last_ts = series.index[-1]
        amount = float(series.iloc[-1])
    except (IndexError, ValueError, TypeError):
        return DividendInfo(ticker=sym)
    payment_date = last_ts.date() if hasattr(last_ts, "date") else None
    return DividendInfo(
        ticker=sym,
        amount=amount,
        payment_date=payment_date,
        is_forward_looking=False,
    )
