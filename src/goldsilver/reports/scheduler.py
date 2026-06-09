"""Asyncio interval scheduler: fire a full-watchlist report run on each boundary."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

from goldsilver.data.session import STOCKHOLM, stockholm_now
from goldsilver.reports.report_service import ReportService

EnabledProvider = Callable[[], bool]
IntervalProvider = Callable[[], int]


def seconds_until_next_boundary(now_local: datetime, interval_minutes: int) -> float:
    """Seconds from now to the next wall-clock boundary aligned to the interval."""
    local = now_local.astimezone(STOCKHOLM)
    interval = max(1, interval_minutes) * 60
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = (local - midnight).total_seconds()
    steps = int(elapsed // interval) + 1
    delay = steps * interval - elapsed
    if delay <= 0:
        delay += interval
    return delay


class ReportScheduler:
    def __init__(
        self,
        service: ReportService,
        *,
        enabled: EnabledProvider,
        interval_minutes: IntervalProvider,
    ) -> None:
        self._service = service
        self._enabled = enabled
        self._interval = interval_minutes
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    async def run_loop(self) -> None:
        while not self._stop.is_set():
            delay = seconds_until_next_boundary(stockholm_now(), self._interval())
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
                return  # stop requested during the wait
            except asyncio.TimeoutError:
                pass
            if self._stop.is_set():
                return
            if not self._enabled():
                continue
            try:
                await self._service.run_all()
            except Exception:
                # A run failure must not kill the scheduler; per-run errors are recorded.
                continue
