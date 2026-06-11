"""Polls FRED for the 10Y TIPS real yield (DFII10) a few times per day."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import httpx
from pydantic import ValidationError

from goldsilver.data.http import make_client
from goldsilver.data.models_macro import RealYieldPoint

RealYieldHandler = Callable[[RealYieldPoint | None], Awaitable[None] | None]

FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_KEY_ENV = "GOLDSILVER_FRED_KEY"
REAL_YIELD_SERIES = "DFII10"
REAL_YIELD_REFRESH_S = 4 * 3600.0

_log = logging.getLogger(__name__)


def parse_observations(payload: dict[str, Any]) -> RealYieldPoint | None:
    """Newest-first FRED observations → latest + previous valid values."""
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return None
    valid: list[tuple[date, float]] = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        raw = str(obs.get("value", ".")).strip()
        if raw in (".", ""):
            continue
        try:
            valid.append((date.fromisoformat(str(obs.get("date"))), float(raw)))
        except ValueError:
            continue
        if len(valid) == 2:
            break
    if not valid:
        return None
    try:
        return RealYieldPoint(
            value=valid[0][1],
            previous=valid[1][1] if len(valid) > 1 else None,
            asof=valid[0][0],
        )
    except ValidationError:
        return None


class RealYieldService:
    def __init__(
        self,
        handler: RealYieldHandler | None = None,
        *,
        refresh_interval_s: float = REAL_YIELD_REFRESH_S,
    ) -> None:
        self._handler = handler
        self._refresh_interval_s = refresh_interval_s
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="real-yield-loop")

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
        key = os.environ.get(FRED_KEY_ENV, "").strip()
        if not key:
            # No key configured: tell the tile explicitly rather than staying blank.
            await self._emit(None)
            return
        try:
            async with make_client(timeout=20.0) as client:
                response = await client.get(
                    FRED_OBS_URL,
                    params={
                        "series_id": REAL_YIELD_SERIES,
                        "api_key": key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 10,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            _log.warning("real yield fetch failed", exc_info=True)
            return
        point = parse_observations(payload)
        if point is not None:
            await self._emit(point)

    async def _emit(self, point: RealYieldPoint | None) -> None:
        if self._handler is None:
            return
        result = self._handler(point)
        if asyncio.iscoroutine(result):
            await result
