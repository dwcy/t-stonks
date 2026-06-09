"""Render tests for the macro calendar panel: impact tag column + released figures."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from goldsilver.data.models_macro import CalendarDay, CalendarEvent, CalendarSnapshot
from goldsilver.widgets.calendar_panel import CalendarPanel

STOCKHOLM = ZoneInfo("Europe/Stockholm")


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield CalendarPanel()


def _today_snapshot(*events: CalendarEvent) -> CalendarSnapshot:
    today = datetime.now(STOCKHOLM).date()
    days = [CalendarDay(date=today, bucket="today", events=tuple(events))]
    for offset in range(1, 6):
        d = date.fromordinal(today.toordinal() + offset)
        days.append(CalendarDay(date=d, bucket="upcoming", events=()))
    return CalendarSnapshot(
        days=tuple(days),
        fetched_at=datetime.now(timezone.utc),
        status="ok",
    )


def _high_event() -> CalendarEvent:
    today = datetime.now(STOCKHOLM).date()
    return CalendarEvent(
        source="FED",
        title="CPI (May)",
        scheduled_time=datetime(
            today.year, today.month, today.day, 14, 30, tzinfo=STOCKHOLM
        ),
        importance="HIGH",
    )


@pytest.mark.asyncio
async def test_today_high_event_renders_impact_tag() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        panel = app.query_one(CalendarPanel)
        panel.apply_snapshot(_today_snapshot(_high_event()))
        await pilot.pause()
        body = str(app.query_one("#cal-today", Static).render())

    assert "HIGH" in body


@pytest.mark.asyncio
async def test_event_at_returns_rendered_event() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        panel = app.query_one(CalendarPanel)
        panel.apply_snapshot(_today_snapshot(_high_event()))
        await pilot.pause()

        assert panel.event_at(0) is not None
        assert panel.event_at(0).title == "CPI (May)"
        assert panel.event_at(9) is None


@pytest.mark.asyncio
async def test_event_row_carries_click_meta() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        panel = app.query_one(CalendarPanel)
        panel.apply_snapshot(_today_snapshot(_high_event()))
        await pilot.pause()
        rendered = app.query_one("#cal-today", Static).render()

    clicks = [
        getattr(span.style, "meta", {}).get("@click")
        for span in rendered.spans
        if not isinstance(span.style, str) and getattr(span.style, "meta", None)
    ]
    assert "app.show_calendar_event(0)" in clicks


@pytest.mark.asyncio
async def test_released_event_renders_actual_figure() -> None:
    event = _high_event().model_copy(
        update={
            "status": "RELEASED",
            "actual": "3.2%",
            "forecast": "3.1%",
            "previous": "3.0%",
        }
    )
    app = _Harness()
    async with app.run_test() as pilot:
        panel = app.query_one(CalendarPanel)
        panel.apply_snapshot(_today_snapshot(event))
        await pilot.pause()
        body = str(app.query_one("#cal-today", Static).render())

    assert "3.2%" in body
