"""Polls a national equity index's current level via yfinance.

One parameterized service instead of a copy per exchange (DAX/CAC 40/FTSE 100/
Nikkei 225) — the existing Swedish OMX tracking (omx_service.py) stays separate
since it drives a much richer weekly-calendar widget these tiles don't need.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from goldsilver.data.models_macro import IndexPoint, IndexSymbol
from goldsilver.data.yf_daily import fetch_daily_close_pair

IndexHandler = Callable[[IndexPoint], Awaitable[None] | None]
IndexStaleHandler = Callable[[IndexSymbol, datetime], Awaitable[None] | None]

INDEX_REFRESH_INTERVAL_S = 60.0


@dataclass(frozen=True, slots=True)
class IndexDefinition:
    yf_symbol: str
    tz: ZoneInfo
    open_time: time
    close_time: time


INDEX_DEFINITIONS: dict[IndexSymbol, IndexDefinition] = {
    "DAX": IndexDefinition(
        "^GDAXI", ZoneInfo("Europe/Berlin"), time(9, 0), time(17, 30)
    ),
    "CAC40": IndexDefinition(
        "^FCHI", ZoneInfo("Europe/Paris"), time(9, 0), time(17, 30)
    ),
    "FTSE100": IndexDefinition(
        "^FTSE", ZoneInfo("Europe/London"), time(8, 0), time(16, 30)
    ),
    "NIKKEI225": IndexDefinition(
        "^N225", ZoneInfo("Asia/Tokyo"), time(9, 0), time(15, 0)
    ),
}


def _is_session_open(definition: IndexDefinition, now_utc: datetime) -> bool:
    local = now_utc.astimezone(definition.tz)
    return (
        local.weekday() < 5
        and definition.open_time <= local.time() <= definition.close_time
    )


class IndexService:
    """One instance per exchange; mirrors CommodityService's poll/emit shape."""

    def __init__(
        self,
        symbol: IndexSymbol,
        handler: IndexHandler | None = None,
        stale_handler: IndexStaleHandler | None = None,
        *,
        refresh_interval_s: float = INDEX_REFRESH_INTERVAL_S,
    ) -> None:
        self._symbol = symbol
        self._definition = INDEX_DEFINITIONS[symbol]
        self._handler = handler
        self._stale_handler = stale_handler
        self._refresh_interval_s = refresh_interval_s
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(
                self._run(), name=f"index-{self._symbol}-loop"
            )

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
        point = await self._fetch()
        if point is None:
            await self._emit_stale()
            return
        await self._emit(point)

    async def _fetch(self) -> IndexPoint | None:
        pair = await asyncio.to_thread(
            fetch_daily_close_pair, self._definition.yf_symbol
        )
        if pair is None:
            return None
        level, previous_close, last_ts = pair
        try:
            return IndexPoint(
                symbol=self._symbol,
                level=level,
                previous_close=previous_close,
                session_open=_is_session_open(
                    self._definition, datetime.now(timezone.utc)
                ),
                time=last_ts,
            )
        except ValidationError:
            return None

    async def _emit(self, point: IndexPoint) -> None:
        if self._handler is None:
            return
        result = self._handler(point)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_stale(self) -> None:
        if self._stale_handler is None:
            return
        result = self._stale_handler(self._symbol, datetime.now(timezone.utc))
        if asyncio.iscoroutine(result):
            await result
