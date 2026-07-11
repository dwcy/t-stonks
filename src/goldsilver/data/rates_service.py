"""Polls the current USA (FRED DFF) and Sweden (Riksbank) central bank policy rates."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from goldsilver.data.fred import fetch_fred_pair, fred_api_key
from goldsilver.data.models_macro import RatePoint, RateSource
from goldsilver.data.riksbank_client import fetch_policy_rate

RateHandler = Callable[[RatePoint | None], Awaitable[None] | None]

FED_FUNDS_SERIES = "DFF"
RATE_REFRESH_S = 4 * 3600.0

_log = logging.getLogger(__name__)


class RateService:
    """One instance per source — mirrors RealYieldService's start/stop/refresh shape."""

    def __init__(
        self,
        source: RateSource,
        handler: RateHandler | None = None,
        *,
        refresh_interval_s: float = RATE_REFRESH_S,
    ) -> None:
        self._source = source
        self._handler = handler
        self._refresh_interval_s = refresh_interval_s
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(
                self._run(), name=f"rate-{self._source}-loop"
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
        if self._source == "fed":
            await self._refresh_fed()
        else:
            await self._refresh_riksbank()

    async def _refresh_fed(self) -> None:
        key = fred_api_key()
        if not key:
            await self._emit(None)
            return
        try:
            obs = await fetch_fred_pair(FED_FUNDS_SERIES, api_key=key)
        except (httpx.HTTPError, ValueError):
            _log.warning("Fed funds rate fetch failed", exc_info=True)
            return
        if obs is None:
            return
        await self._emit(
            RatePoint(
                value=obs.value, previous=obs.previous, asof=obs.asof, source="fed"
            )
        )

    async def _refresh_riksbank(self) -> None:
        obs = await fetch_policy_rate()
        if obs is None:
            return
        await self._emit(
            RatePoint(
                value=obs.value, previous=obs.previous, asof=obs.asof, source="riksbank"
            )
        )

    async def _emit(self, point: RatePoint | None) -> None:
        if self._handler is None:
            return
        result = self._handler(point)
        if asyncio.iscoroutine(result):
            await result
