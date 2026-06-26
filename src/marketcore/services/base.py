"""PollingService — shared start/stop/refresh loop for async data feeds."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Generic, TypeVar

T = TypeVar("T")


class PollingService(Generic[T]):
    """Base for services that poll an upstream on a fixed interval.

    Subclasses implement ``_refresh_once``; this base owns the task lifecycle
    (start/stop/refresh_now), the stop event, and the emit/stale plumbing.
    """

    def __init__(
        self,
        handler,
        stale_handler,
        refresh_interval_s: float,
        task_name: str,
    ) -> None:
        self._handler = handler
        self._stale_handler = stale_handler
        self._refresh_interval_s = refresh_interval_s
        self._task_name = task_name
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def _should_start(self) -> bool:
        return True

    def start(self) -> None:
        if not self._should_start():
            return
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name=self._task_name)

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
        raise NotImplementedError

    async def _emit(self, payload: T) -> None:
        if self._handler is None:
            return
        result = self._handler(payload)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_stale(self) -> None:
        if self._stale_handler is None:
            return
        result = self._stale_handler(datetime.now(timezone.utc))
        if asyncio.iscoroutine(result):
            await result
