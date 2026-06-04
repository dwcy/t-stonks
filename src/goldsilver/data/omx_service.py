from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, time, timedelta, timezone

import yfinance as yf
from pydantic import ValidationError

from goldsilver.data.models_macro import OmxDay, OmxSnapshot
from goldsilver.data.session import STOCKHOLM


OmxHandler = Callable[[OmxSnapshot], Awaitable[None] | None]
OmxStaleHandler = Callable[[datetime], Awaitable[None] | None]

OMX_REFRESH_INTERVAL_S = 60.0
OMX_SYMBOL = "^OMX"
HISTORY_DAYS = 25
OMX_OPEN = time(9, 0)
OMX_CLOSE = time(17, 30)
OMX_EARLY_CLOSE_BUFFER_MIN = 60


class OmxService:
    def __init__(
        self,
        handler: OmxHandler | None = None,
        stale_handler: OmxStaleHandler | None = None,
        *,
        refresh_interval_s: float = OMX_REFRESH_INTERVAL_S,
    ) -> None:
        self._handler = handler
        self._stale_handler = stale_handler
        self._refresh_interval_s = refresh_interval_s
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="omx-loop")

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
        snapshot = await self._fetch()
        if snapshot is None:
            await self._emit_stale()
            return
        await self._emit(snapshot)

    async def _fetch(self) -> OmxSnapshot | None:
        def _sync() -> OmxSnapshot | None:
            try:
                ticker = yf.Ticker(OMX_SYMBOL)
                daily = ticker.history(period="1y", interval="1d")
                intraday = ticker.history(period="1d", interval="5m")
            except Exception:
                return None
            if daily is None or len(daily) < HISTORY_DAYS + 2:
                return None
            closes = [float(c) for c in daily["Close"].tolist() if c == c]
            dates = [t.to_pydatetime().date() for t in daily.index]
            if len(closes) < HISTORY_DAYS + 2:
                return None

            history: list[OmxDay] = []
            start = max(1, len(closes) - HISTORY_DAYS)
            for i in range(start, len(closes)):
                prev = closes[i - 1]
                pct = (closes[i] - prev) / prev * 100.0 if prev else 0.0
                history.append(
                    OmxDay(date=dates[i], close=closes[i], change_percent=pct)
                )

            fast_price: float | None = None
            fast_prev_close: float | None = None
            try:
                fi = ticker.fast_info
                fp = fi.last_price
                fpc = fi.previous_close
                if fp is not None and fp > 0:
                    fast_price = float(fp)
                if fpc is not None and fpc > 0:
                    fast_prev_close = float(fpc)
            except Exception:
                pass

            if intraday is not None and len(intraday) > 0:
                intraday_price = float(intraday["Close"].iloc[-1])
                latest_ts = intraday.index[-1].to_pydatetime()
            else:
                intraday_price = closes[-1]
                latest_ts = datetime.combine(dates[-1], time(17, 30), tzinfo=STOCKHOLM)
            if latest_ts.tzinfo is None:
                latest_ts = latest_ts.replace(tzinfo=timezone.utc)

            current_price = fast_price if fast_price is not None else intraday_price

            session_date = latest_ts.astimezone(STOCKHOLM).date()
            if fast_prev_close is not None:
                reference_close = fast_prev_close
            elif session_date != dates[-1]:
                reference_close = closes[-1]
            else:
                reference_close = closes[-2]
            current_pct = (
                (current_price - reference_close) / reference_close * 100.0
                if reference_close
                else 0.0
            )

            now_stk = datetime.now(STOCKHOLM)
            latest_local = latest_ts.astimezone(STOCKHOLM)
            market_open = (
                now_stk.weekday() < 5
                and OMX_OPEN <= now_stk.time() <= OMX_CLOSE
                and (now_stk - latest_local) <= timedelta(minutes=20)
            )

            current_year = now_stk.year
            ytd_ref_close: float | None = None
            for d, c in zip(dates, closes):
                if d.year == current_year:
                    break
                ytd_ref_close = c
            if ytd_ref_close is None:
                ytd_ref_close = closes[0]
            ytd_change = (
                (current_price - ytd_ref_close) / ytd_ref_close * 100.0
                if ytd_ref_close
                else None
            )

            try:
                return OmxSnapshot(
                    days=tuple(history),
                    current_price=current_price,
                    current_change_percent=current_pct,
                    fetched_at=datetime.now(timezone.utc),
                    market_open=market_open,
                    latest_session_date=latest_local.date(),
                    latest_session_close_time=latest_ts,
                    ytd_change_percent=ytd_change,
                )
            except ValidationError:
                return None

        return await asyncio.to_thread(_sync)

    async def _emit(self, snapshot: OmxSnapshot) -> None:
        if self._handler is None:
            return
        result = self._handler(snapshot)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_stale(self) -> None:
        if self._stale_handler is None:
            return
        result = self._stale_handler(datetime.now(timezone.utc))
        if asyncio.iscoroutine(result):
            await result
