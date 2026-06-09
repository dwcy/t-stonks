from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, ValidationError

from goldsilver.data.calendar_actuals import (
    ActualsFetcher,
    due_events,
    merge_event,
)
from goldsilver.data.calendar_static import load_static_events, window_around
from goldsilver.data.models_macro import (
    CalendarDay,
    CalendarEvent,
    CalendarSnapshot,
)
from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.claude_runner import find_claude

if TYPE_CHECKING:
    from goldsilver.data.settings import CalendarSettings


CalendarHandler = Callable[[CalendarSnapshot], Awaitable[None] | None]
CalendarSettingsProvider = Callable[[], "CalendarSettings"]

FRED_URL = "https://api.stlouisfed.org/fred/releases/dates"
FRED_KEY_ENV = "GOLDSILVER_FRED_KEY"
CALENDAR_REFRESH_INTERVAL_S = 600.0
ACTUALS_CHECK_INTERVAL_S = 60.0
_HIGH_IMPORTANCE_RELEASES = frozenset(
    {
        "Consumer Price Index",
        "Producer Price Index",
        "Employment Situation",
        "Gross Domestic Product",
        "Personal Income and Outlays",
        "Retail Trade",
        "Industrial Production and Capacity Utilization",
    }
)


class _FredReleaseDate(BaseModel):
    release_id: int
    release_name: str
    date: date


class _FredResponse(BaseModel):
    release_dates: list[_FredReleaseDate] = []


class CalendarService:
    def __init__(
        self,
        handler: CalendarHandler | None = None,
        *,
        refresh_interval_s: float = CALENDAR_REFRESH_INTERVAL_S,
        fred_key: str | None = None,
        actuals_settings_provider: CalendarSettingsProvider | None = None,
    ) -> None:
        self._handler = handler
        self._refresh_interval_s = refresh_interval_s
        self._fred_key = (
            fred_key if fred_key is not None else os.environ.get(FRED_KEY_ENV)
        )
        self._actuals_provider = actuals_settings_provider
        self._task: asyncio.Task[None] | None = None
        self._actuals_task: asyncio.Task[None] | None = None
        self._actuals_fetcher: ActualsFetcher | None = None
        self._stop = asyncio.Event()
        self._last_snapshot: CalendarSnapshot | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="calendar-loop")
        if self._actuals_provider is not None and (
            self._actuals_task is None or self._actuals_task.done()
        ):
            self._actuals_task = asyncio.create_task(
                self._actuals_loop(), name="calendar-actuals-loop"
            )

    async def stop(self) -> None:
        self._stop.set()
        for attr in ("_task", "_actuals_task"):
            task = getattr(self, attr)
            if task is not None:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                setattr(self, attr, None)

    async def refresh_now(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await self._refresh_once(client)

    async def _run(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await self._refresh_once(client)
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._refresh_interval_s
                    )
                    return
                except asyncio.TimeoutError:
                    pass
                await self._refresh_once(client)

    async def _refresh_once(self, client: httpx.AsyncClient) -> None:
        today_stk = datetime.now(STOCKHOLM).date()
        window_start, window_end = window_around(today_stk)

        static_events = load_static_events(window_start, window_end)
        fred_events = await self._fetch_fred(client, window_start, window_end)

        all_events = static_events + fred_events
        snapshot = self._build_snapshot(today_stk, all_events, status="ok")
        self._last_snapshot = snapshot
        await self._emit(snapshot)

    async def _fetch_fred(
        self,
        client: httpx.AsyncClient,
        window_start: date,
        window_end: date,
    ) -> list[CalendarEvent]:
        if not self._fred_key:
            return []
        params = {
            "api_key": self._fred_key,
            "file_type": "json",
            "realtime_start": window_start.isoformat(),
            "realtime_end": window_end.isoformat(),
            "include_release_dates_with_no_data": "true",
            "limit": "1000",
            "sort_order": "asc",
        }
        try:
            response = await client.get(FRED_URL, params=params)
            response.raise_for_status()
            payload = _FredResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError):
            return []

        events: list[CalendarEvent] = []
        for rd in payload.release_dates:
            if not (window_start <= rd.date <= window_end):
                continue
            try:
                event = CalendarEvent(
                    source="FED",
                    title=rd.release_name,
                    scheduled_time=datetime(
                        rd.date.year,
                        rd.date.month,
                        rd.date.day,
                        12,
                        0,
                        tzinfo=timezone.utc,
                    ),
                    all_day=True,
                    importance="HIGH"
                    if rd.release_name in _HIGH_IMPORTANCE_RELEASES
                    else "MED",
                )
            except ValidationError:
                continue
            events.append(event)
        return events

    def _build_snapshot(
        self,
        today_stk: date,
        events: list[CalendarEvent],
        *,
        status: str,
    ) -> CalendarSnapshot:
        by_date: dict[date, list[CalendarEvent]] = {}
        for ev in events:
            d = ev.scheduled_time.astimezone(STOCKHOLM).date()
            by_date.setdefault(d, []).append(ev)

        days: list[CalendarDay] = []
        for offset in range(0, 6):
            d = today_stk + timedelta(days=offset)
            bucket = "today" if offset == 0 else "upcoming"
            day_events = sorted(by_date.get(d, []), key=lambda e: e.scheduled_time)
            days.append(CalendarDay(date=d, bucket=bucket, events=tuple(day_events)))
        return CalendarSnapshot(
            days=tuple(days),
            fetched_at=datetime.now(timezone.utc),
            status=status,  # type: ignore[arg-type]
        )

    async def _emit(self, snapshot: CalendarSnapshot) -> None:
        if self._handler is None:
            return
        result = self._handler(snapshot)
        if asyncio.iscoroutine(result):
            await result

    async def _actuals_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=ACTUALS_CHECK_INTERVAL_S
                )
                return
            except asyncio.TimeoutError:
                pass
            try:
                await self._check_due()
            except Exception:
                pass

    async def _check_due(self) -> None:
        provider = self._actuals_provider
        snapshot = self._last_snapshot
        if provider is None or snapshot is None:
            return
        cfg = provider()
        if not cfg.actuals_enabled or find_claude() is None:
            return
        if self._actuals_fetcher is None:
            self._actuals_fetcher = ActualsFetcher(
                max_concurrency=cfg.actuals_max_concurrency,
                timeout_seconds=cfg.actuals_timeout_seconds,
            )
        fetcher = self._actuals_fetcher
        now = datetime.now(timezone.utc)
        pending = [
            e
            for e in due_events(snapshot, now, cfg.actuals_grace_minutes)
            if fetcher.should_fetch(e)
        ]
        if not pending:
            return
        results = await asyncio.gather(
            *(fetcher.fetch(e) for e in pending), return_exceptions=True
        )
        updated = [r for r in results if isinstance(r, CalendarEvent)]
        if not updated:
            return
        merged = self._last_snapshot or snapshot
        for event in updated:
            merged = merge_event(merged, event)
        self._last_snapshot = merged
        await self._emit(merged)
