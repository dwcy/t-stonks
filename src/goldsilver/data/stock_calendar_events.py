"""Turn mini-graph tickers' forward corporate calendars into CalendarEvents."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time

from marketcore.models_macro import CalendarEvent, EventImportance, StockCalendar
from marketcore.services.stock_service import fetch_stock_calendar

from goldsilver.data.session import STOCKHOLM

_EARNINGS_IMPORTANCE: EventImportance = "HIGH"
_EX_DIV_IMPORTANCE: EventImportance = "MED"
_PAY_IMPORTANCE: EventImportance = "LOW"


def _at_noon_cet(d: date) -> datetime:
    return datetime.combine(d, time(12, 0), tzinfo=STOCKHOLM)


def _event(
    ticker: str, d: date, kind: str, importance: EventImportance
) -> CalendarEvent:
    return CalendarEvent(
        source="STOCK",
        title=f"{ticker} {kind}",
        scheduled_time=_at_noon_cet(d),
        all_day=True,
        importance=importance,
    )


def calendar_to_events(
    cal: StockCalendar, window_start: date, window_end: date
) -> list[CalendarEvent]:
    def in_window(d: date | None) -> bool:
        return d is not None and window_start <= d <= window_end

    events: list[CalendarEvent] = []
    for earnings_date in cal.earnings_dates:
        if in_window(earnings_date):
            events.append(
                _event(cal.ticker, earnings_date, "earnings", _EARNINGS_IMPORTANCE)
            )
    if in_window(cal.ex_dividend_date):
        assert cal.ex_dividend_date is not None
        events.append(
            _event(cal.ticker, cal.ex_dividend_date, "ex-dividend", _EX_DIV_IMPORTANCE)
        )
    if in_window(cal.dividend_pay_date):
        assert cal.dividend_pay_date is not None
        events.append(
            _event(cal.ticker, cal.dividend_pay_date, "dividend", _PAY_IMPORTANCE)
        )
    return events


async def fetch_stock_events(
    tickers: list[str], window_start: date, window_end: date
) -> list[CalendarEvent]:
    """Fetch each ticker's forward calendar concurrently, keep events in window."""
    if not tickers:
        return []
    results = await asyncio.gather(
        *(asyncio.to_thread(fetch_stock_calendar, t) for t in tickers),
        return_exceptions=True,
    )
    events: list[CalendarEvent] = []
    for result in results:
        if isinstance(result, StockCalendar):
            events.extend(calendar_to_events(result, window_start, window_end))
    return events
