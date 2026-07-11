from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from goldsilver.data.http import make_client
from goldsilver.data.models_macro import CommodityQuote, CommoditySymbol
from goldsilver.data.yf_daily import fetch_daily_close_pair


CommodityHandler = Callable[[CommodityQuote], Awaitable[None] | None]
CommodityStaleHandler = Callable[[CommoditySymbol, datetime], Awaitable[None] | None]

COMMODITY_REFRESH_INTERVAL_S = 60.0
_YF_SYMBOL: dict[CommoditySymbol, str] = {
    "BRENT": "BZ=F",
    "BTC": "BTC-USD",
    "DXY": "DX-Y.NYB",
}
_ALL_SYMBOLS: tuple[CommoditySymbol, ...] = ("BRENT", "COPPER", "BTC", "DXY")

# Copper reads from Avanza (LME 3-month, USD/tonne) like gold/silver, so the value
# matches the Avanza app — COMEX HG=F is USD/lb and mismatches by the unit factor.
AVANZA_INSTRUMENT_URL = "https://www.avanza.se/_api/market-guide/stock/{orderbook_id}"
AVANZA_COPPER_ORDERBOOK = "18989"


async def fetch_commodity_quote(symbol: CommoditySymbol) -> CommodityQuote | None:
    """One-shot fetch for a single commodity — reused by the poller and by the
    report engine's reference-quote lookup (reports/reference_quote.py)."""
    if symbol == "COPPER":
        return await _fetch_copper_avanza()
    yf_symbol = _YF_SYMBOL[symbol]
    pair = await asyncio.to_thread(fetch_daily_close_pair, yf_symbol)
    if pair is None:
        return None
    price, previous_close, last_ts = pair
    try:
        return CommodityQuote(
            symbol=symbol,
            price=price,
            previous_close=previous_close,
            time=last_ts,
        )
    except ValidationError:
        return None


async def _fetch_copper_avanza() -> CommodityQuote | None:
    url = AVANZA_INSTRUMENT_URL.format(orderbook_id=AVANZA_COPPER_ORDERBOOK)
    try:
        async with make_client(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        price = float(payload["quote"]["last"])
        previous_close = float(payload["historicalClosingPrices"]["oneDay"])
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None
    try:
        return CommodityQuote(
            symbol="COPPER",
            price=price,
            previous_close=previous_close,
            time=datetime.now(timezone.utc),
        )
    except ValidationError:
        return None


class CommodityService:
    def __init__(
        self,
        handler: CommodityHandler | None = None,
        stale_handler: CommodityStaleHandler | None = None,
        *,
        refresh_interval_s: float = COMMODITY_REFRESH_INTERVAL_S,
    ) -> None:
        self._handler = handler
        self._stale_handler = stale_handler
        self._refresh_interval_s = refresh_interval_s
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="commodity-loop")

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
        symbols = _ALL_SYMBOLS
        results = await asyncio.gather(
            *[self._fetch(s) for s in symbols],
            return_exceptions=True,
        )
        for symbol, result in zip(symbols, results):
            if isinstance(result, CommodityQuote):
                await self._emit(result)
            else:
                await self._emit_stale(symbol)

    async def _fetch(self, symbol: CommoditySymbol) -> CommodityQuote | None:
        return await fetch_commodity_quote(symbol)

    async def _emit(self, quote: CommodityQuote) -> None:
        if self._handler is None:
            return
        result = self._handler(quote)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_stale(self, symbol: CommoditySymbol) -> None:
        if self._stale_handler is None:
            return
        result = self._stale_handler(symbol, datetime.now(timezone.utc))
        if asyncio.iscoroutine(result):
            await result
