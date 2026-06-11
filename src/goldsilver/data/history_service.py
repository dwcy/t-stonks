"""Archives each trading day's 1m bars: startup backfill + end-of-day save."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date

from goldsilver.data.history_store import save_day, split_by_day
from goldsilver.data.models import GOLD, SILVER, Bar
from goldsilver.data.session import stockholm_now
from goldsilver.data.trading_hours import is_open

FetchHistory = Callable[[str, str, str], Awaitable[list[Bar]]]

EOD_TICK_S = 60.0

_log = logging.getLogger(__name__)


class HistoryService:
    def __init__(self, fetch: FetchHistory) -> None:
        self._fetch = fetch
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._was_open: bool | None = None
        self._saved_close_for: date | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="history-archive")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _run(self) -> None:
        await self._backfill()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=EOD_TICK_S)
                return
            except asyncio.TimeoutError:
                pass
            await self._check_eod()

    async def _backfill(self) -> None:
        for symbol in (GOLD, SILVER):
            try:
                bars = await self._fetch(symbol, "7d", "1m")
            except Exception:
                _log.exception("history backfill fetch failed for %s", symbol)
                continue
            for day, day_bars in split_by_day(bars).items():
                save_day(symbol, day, day_bars)

    async def _check_eod(self) -> None:
        now = stockholm_now()
        open_now = is_open(now)
        if self._was_open and not open_now:
            await self._save_today(now.date())
        self._was_open = open_now

    async def _save_today(self, today: date) -> None:
        if self._saved_close_for == today:
            return
        for symbol in (GOLD, SILVER):
            try:
                bars = await self._fetch(symbol, "2d", "1m")
            except Exception:
                _log.exception("end-of-day history fetch failed for %s", symbol)
                continue
            day_bars = split_by_day(bars).get(today)
            if day_bars:
                save_day(symbol, today, day_bars)
        self._saved_close_for = today
