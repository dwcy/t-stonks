from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import yfinance as yf
from pydantic import ValidationError

from goldsilver.data.models_macro import FxPair, FxRate


FxHandler = Callable[[FxRate], Awaitable[None] | None]
FxStaleHandler = Callable[[FxPair, datetime], Awaitable[None] | None]

FX_REFRESH_INTERVAL_S = 60.0
_YF_SYMBOL: dict[FxPair, str] = {
    "USDSEK": "SEK=X",
    "CADSEK": "CADSEK=X",
    "EURSEK": "EURSEK=X",
}


class FxService:
    def __init__(
        self,
        handler: FxHandler | None = None,
        stale_handler: FxStaleHandler | None = None,
        *,
        refresh_interval_s: float = FX_REFRESH_INTERVAL_S,
    ) -> None:
        self._handler = handler
        self._stale_handler = stale_handler
        self._refresh_interval_s = refresh_interval_s
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="fx-loop")

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
        pairs = tuple(_YF_SYMBOL.keys())
        results = await asyncio.gather(
            *[self._fetch_pair(p) for p in pairs],
            return_exceptions=True,
        )
        for pair, result in zip(pairs, results):
            if isinstance(result, FxRate):
                await self._emit(result)
            else:
                await self._emit_stale(pair)

    async def _fetch_pair(self, pair: FxPair) -> FxRate | None:
        yf_symbol = _YF_SYMBOL[pair]

        def _sync() -> FxRate | None:
            try:
                intraday = yf.Ticker(yf_symbol).history(
                    period="1d", interval="1m"
                )
                daily = yf.Ticker(yf_symbol).history(
                    period="5d", interval="1d"
                )
            except Exception:
                return None
            if intraday is None or len(intraday) == 0:
                return None
            if daily is None or len(daily) < 2:
                return None
            current = float(intraday["Close"].iloc[-1])
            prev_close = float(daily["Close"].iloc[-2])
            ts = intraday.index[-1].to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            try:
                return FxRate(
                    pair=pair,
                    rate=current,
                    previous_close=prev_close,
                    time=ts.astimezone(timezone.utc),
                )
            except ValidationError:
                return None

        return await asyncio.to_thread(_sync)

    async def _emit(self, rate: FxRate) -> None:
        if self._handler is None:
            return
        result = self._handler(rate)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_stale(self, pair: FxPair) -> None:
        if self._stale_handler is None:
            return
        result = self._stale_handler(pair, datetime.now(timezone.utc))
        if asyncio.iscoroutine(result):
            await result
