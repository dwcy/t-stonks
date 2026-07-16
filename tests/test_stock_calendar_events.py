"""Tests for converting stock forward-calendars into windowed CalendarEvents."""

from __future__ import annotations

import asyncio
from datetime import date

from marketcore.models_macro import StockCalendar

from goldsilver.data import stock_calendar_events
from goldsilver.data.stock_calendar_events import (
    calendar_to_events,
    fetch_stock_events,
)


def test_calendar_to_events_builds_all_three_kinds() -> None:
    cal = StockCalendar(
        ticker="MSFT",
        earnings_dates=(date(2026, 7, 29),),
        ex_dividend_date=date(2026, 7, 30),
        dividend_pay_date=date(2026, 7, 31),
    )

    events = calendar_to_events(cal, date(2026, 7, 1), date(2026, 8, 31))

    titles = {e.title: e.importance for e in events}
    assert titles == {
        "MSFT earnings": "HIGH",
        "MSFT ex-dividend": "MED",
        "MSFT dividend": "LOW",
    }


def test_calendar_to_events_are_all_day_stock_source() -> None:
    cal = StockCalendar(ticker="AAPL", earnings_dates=(date(2026, 7, 30),))

    event = calendar_to_events(cal, date(2026, 7, 1), date(2026, 8, 31))[0]

    assert event.source == "STOCK"
    assert event.all_day is True


def test_calendar_to_events_excludes_dates_outside_window() -> None:
    cal = StockCalendar(
        ticker="MSFT",
        earnings_dates=(date(2026, 7, 29),),
        ex_dividend_date=date(2026, 12, 1),
    )

    events = calendar_to_events(cal, date(2026, 7, 1), date(2026, 7, 31))

    assert [e.title for e in events] == ["MSFT earnings"]


def test_calendar_to_events_empty_when_no_dates() -> None:
    cal = StockCalendar(ticker="BRK-A")

    assert calendar_to_events(cal, date(2026, 7, 1), date(2026, 7, 31)) == []


def test_fetch_stock_events_skips_failed_tickers(monkeypatch) -> None:
    def fake_fetch(sym: str) -> StockCalendar:
        if sym == "BOOM":
            raise RuntimeError("network down")
        return StockCalendar(ticker=sym, earnings_dates=(date(2026, 7, 20),))

    monkeypatch.setattr(stock_calendar_events, "fetch_stock_calendar", fake_fetch)

    events = asyncio.run(
        fetch_stock_events(
            ["MSFT", "BOOM", "AAPL"], date(2026, 7, 1), date(2026, 7, 31)
        )
    )

    assert sorted(e.title for e in events) == ["AAPL earnings", "MSFT earnings"]


def test_fetch_stock_events_empty_ticker_list() -> None:
    events = asyncio.run(fetch_stock_events([], date(2026, 7, 1), date(2026, 7, 31)))

    assert events == []
