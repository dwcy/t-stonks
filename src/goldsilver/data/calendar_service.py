from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, ValidationError

from goldsilver.data.calendar_actuals import (
    ActualsFetcher,
    due_events,
    merge_event,
    same_day_titles,
)
from goldsilver.data.calendar_actuals_store import CalendarActualsStore, event_key
from goldsilver.data.calendar_expectations import fetch_expected
from goldsilver.data.calendar_static import load_static_events, window_around
from goldsilver.data.fred import fred_api_key
from goldsilver.data.stock_calendar_events import fetch_stock_events
from goldsilver.data.http import make_client
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
StockTickersProvider = Callable[[], list[str]]
FetchStartedHandler = Callable[[str], None]
FetchFinishedHandler = Callable[[str, bool], None]

FRED_URL = "https://api.stlouisfed.org/fred/releases/dates"
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
        actuals_store: CalendarActualsStore | None = None,
        stock_tickers_provider: StockTickersProvider | None = None,
        on_fetch_started: FetchStartedHandler | None = None,
        on_fetch_finished: FetchFinishedHandler | None = None,
    ) -> None:
        self._handler = handler
        self._refresh_interval_s = refresh_interval_s
        self._fred_key = fred_key if fred_key is not None else fred_api_key()
        self._actuals_provider = actuals_settings_provider
        self._stock_tickers_provider = stock_tickers_provider
        self._actuals_store = actuals_store or CalendarActualsStore()
        self._on_fetch_started = on_fetch_started
        self._on_fetch_finished = on_fetch_finished
        self._task: asyncio.Task[None] | None = None
        self._actuals_task: asyncio.Task[None] | None = None
        self._actuals_fetcher: ActualsFetcher | None = None
        self._stop = asyncio.Event()
        self._last_snapshot: CalendarSnapshot | None = None

    def start(self) -> None:
        self._actuals_store.load()
        self._actuals_store.prune(datetime.now(timezone.utc))
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
        async with make_client(timeout=10.0) as client:
            await self._refresh_once(client)

    async def fetch_actuals_now(self, event: CalendarEvent) -> CalendarEvent | None:
        stored = self._actuals_store.get(event)
        # A cached record only short-circuits if it carries a released actual; a
        # forward-looking preview (actual is None) must not block the real fetch.
        if stored is not None and stored.actual is not None:
            return await self._apply_updated(stored.apply_to(event))
        if find_claude() is None:
            return None
        self._ensure_fetcher()
        assert self._actuals_fetcher is not None
        siblings = self._siblings_for(event)
        updated = await self._actuals_fetcher.fetch(event, siblings)
        if updated is None:
            return None
        self._actuals_store.put(updated)
        return await self._apply_updated(updated)

    async def fetch_expected_now(self, event: CalendarEvent) -> CalendarEvent | None:
        stored = self._actuals_store.get(event)
        if stored is not None:
            return await self._apply_updated(stored.apply_to(event))
        if find_claude() is None:
            return None
        cfg = self._actuals_provider() if self._actuals_provider is not None else None
        timeout = cfg.actuals_timeout_seconds if cfg is not None else 180
        updated = await fetch_expected(
            event, self._siblings_for(event), timeout_seconds=timeout
        )
        if updated is None:
            return None
        self._actuals_store.put(updated)
        return await self._apply_updated(updated)

    def _siblings_for(self, event: CalendarEvent) -> tuple[str, ...]:
        if self._last_snapshot is None:
            return ()
        return same_day_titles(self._last_snapshot, event)

    async def _apply_updated(self, updated: CalendarEvent) -> CalendarEvent:
        base = self._last_snapshot
        if base is not None:
            merged = merge_event(base, updated)
            self._last_snapshot = merged
            await self._emit(merged)
        return updated

    def _ensure_fetcher(self) -> None:
        if self._actuals_fetcher is not None:
            return
        cfg = self._actuals_provider() if self._actuals_provider is not None else None
        self._actuals_fetcher = ActualsFetcher(
            max_concurrency=cfg.actuals_max_concurrency if cfg is not None else 2,
            timeout_seconds=cfg.actuals_timeout_seconds if cfg is not None else 180,
        )

    async def _run(self) -> None:
        async with make_client(timeout=10.0) as client:
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
        stock_events = await self._fetch_stock_events(window_start, window_end)

        all_events = static_events + fred_events + stock_events
        snapshot = self._build_snapshot(today_stk, all_events, status="ok")
        snapshot = self._actuals_store.apply(snapshot)
        self._last_snapshot = snapshot
        await self._emit(snapshot)

    async def _fetch_stock_events(
        self, window_start: date, window_end: date
    ) -> list[CalendarEvent]:
        if self._stock_tickers_provider is None:
            return []
        tickers = self._stock_tickers_provider()
        try:
            return await fetch_stock_events(tickers, window_start, window_end)
        except Exception:
            return []

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
        self._ensure_fetcher()
        assert self._actuals_fetcher is not None
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
            *(
                self._fetch_and_notify(fetcher, e, same_day_titles(snapshot, e))
                for e in pending
            ),
            return_exceptions=True,
        )
        updated = [r for r in results if isinstance(r, CalendarEvent)]
        if not updated:
            return
        merged = self._last_snapshot or snapshot
        for event in updated:
            self._actuals_store.put(event)
            merged = merge_event(merged, event)
        self._last_snapshot = merged
        await self._emit(merged)

    async def _fetch_and_notify(
        self,
        fetcher: ActualsFetcher,
        event: CalendarEvent,
        same_day_events: tuple[str, ...],
    ) -> CalendarEvent | None:
        key = event_key(event)
        if self._on_fetch_started is not None:
            self._on_fetch_started(key)
        ok = False
        try:
            result = await fetcher.fetch(event, same_day_events)
            ok = result is not None
            return result
        finally:
            if self._on_fetch_finished is not None:
                self._on_fetch_finished(key, ok)
