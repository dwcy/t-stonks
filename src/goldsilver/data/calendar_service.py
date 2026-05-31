from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone

import httpx
from pydantic import BaseModel, ValidationError

from goldsilver.data.calendar_static import load_static_events, window_around
from goldsilver.data.models_macro import (
    CalendarDay,
    CalendarEvent,
    CalendarSnapshot,
)
from goldsilver.data.session import STOCKHOLM


CalendarHandler = Callable[[CalendarSnapshot], Awaitable[None] | None]

FRED_URL = "https://api.stlouisfed.org/fred/releases/dates"
FRED_KEY_ENV = "GOLDSILVER_FRED_KEY"
CALENDAR_REFRESH_INTERVAL_S = 600.0
_HIGH_IMPORTANCE_RELEASES = frozenset({
    "Consumer Price Index",
    "Producer Price Index",
    "Employment Situation",
    "Gross Domestic Product",
    "Personal Income and Outlays",
    "Retail Trade",
    "Industrial Production and Capacity Utilization",
})


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
    ) -> None:
        self._handler = handler
        self._refresh_interval_s = refresh_interval_s
        self._fred_key = fred_key if fred_key is not None else os.environ.get(FRED_KEY_ENV)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_snapshot: CalendarSnapshot | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="calendar-loop")

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
                        rd.date.year, rd.date.month, rd.date.day,
                        12, 0, tzinfo=timezone.utc,
                    ),
                    all_day=True,
                    importance="HIGH" if rd.release_name in _HIGH_IMPORTANCE_RELEASES else "MED",
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
            days.append(
                CalendarDay(date=d, bucket=bucket, events=tuple(day_events))
            )
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
