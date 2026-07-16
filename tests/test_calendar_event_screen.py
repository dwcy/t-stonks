"""Smoke tests for the calendar event detail modal."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from goldsilver.data.models_macro import CalendarEvent, EventAnalysis
from goldsilver.widgets.calendar_event_screen import CalendarEventScreen

STOCKHOLM = ZoneInfo("Europe/Stockholm")


def _event(**overrides: object) -> CalendarEvent:
    base = dict(
        source="FED",
        title="CPI (May)",
        scheduled_time=datetime(2026, 6, 10, 14, 30, tzinfo=STOCKHOLM),
        importance="HIGH",
    )
    base.update(overrides)
    return CalendarEvent(**base)  # type: ignore[arg-type]


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield Static("base")


@pytest.mark.asyncio
async def test_modal_without_data_shows_placeholder() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = CalendarEventScreen(_event(), can_fetch=False)
        await app.push_screen(screen)
        await pilot.pause()
        figures = str(screen.query_one("#cal-event-figures", Static).render())

    assert "No forecast or released figures yet." in figures


@pytest.mark.asyncio
async def test_modal_with_released_data_shows_figures() -> None:
    event = _event(status="RELEASED", actual="3.2%", actual_summary="CPI hot.")
    app = _Harness()
    async with app.run_test() as pilot:
        screen = CalendarEventScreen(event, can_fetch=False)
        await app.push_screen(screen)
        await pilot.pause()
        figures = str(screen.query_one("#cal-event-figures", Static).render())

    assert "3.2%" in figures
    assert "CPI hot." in figures


def _preview_event() -> CalendarEvent:
    return _event(
        forecast="3.1%",
        previous="3.0%",
        expected_summary="Consensus sees CPI 3.1%.",
        analysis=EventAnalysis(
            surprise="na", gold="bearish", silver="neutral", usd="bullish"
        ),
    )


@pytest.mark.asyncio
async def test_modal_preview_shows_forecast_figures() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = CalendarEventScreen(_preview_event(), can_fetch=False)
        await app.push_screen(screen)
        await pilot.pause()
        figures = str(screen.query_one("#cal-event-figures", Static).render())

    assert "3.1%" in figures
    assert "Consensus sees CPI 3.1%." in figures


@pytest.mark.asyncio
async def test_modal_preview_labels_impact_as_expected() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = CalendarEventScreen(_preview_event(), can_fetch=False)
        await app.push_screen(screen)
        await pilot.pause()
        analysis = str(screen.query_one("#cal-event-analysis", Static).render())

    assert "Expected impact" in analysis
    assert "Impact read" not in analysis


@pytest.mark.asyncio
async def test_modal_released_labels_impact_as_read() -> None:
    event = _event(
        status="RELEASED",
        actual="3.4%",
        analysis=EventAnalysis(
            surprise="above", gold="bearish", silver="bearish", usd="bullish"
        ),
    )
    app = _Harness()
    async with app.run_test() as pilot:
        screen = CalendarEventScreen(event, can_fetch=False)
        await app.push_screen(screen)
        await pilot.pause()
        analysis = str(screen.query_one("#cal-event-analysis", Static).render())

    assert "Impact read" in analysis
    assert "above forecast" in analysis
