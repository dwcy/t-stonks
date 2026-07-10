"""Mount-and-render smoke tests for the stock chart detail modal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from marketcore.models import Bar
from marketcore.widgets.chart import PriceChart
from marketcore.widgets.daily_change_strip import DailyChangeStrip
from marketcore.widgets.stock_chart_screen import StockChartScreen


def _bars(n: int = 45) -> list[Bar]:
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    return [
        Bar(
            symbol="NVDA",
            time=base + timedelta(days=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.0 + i,
            volume=1000.0,
        )
        for i in range(n)
    ]


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield Static("base")


@pytest.mark.asyncio
async def test_modal_seeds_chart_and_strip() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars())
        await app.push_screen(screen)
        await pilot.pause()

        chart = screen.query_one(PriceChart)
        strip = screen.query_one(DailyChangeStrip)
        assert len(chart._bars) == 45
        strip_text = str(strip.render())
        assert "%" in strip_text


@pytest.mark.asyncio
async def test_modal_handles_fewer_than_forty_days() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars(5))
        await app.push_screen(screen)
        await pilot.pause()

        strip = screen.query_one(DailyChangeStrip)
        strip_text = str(strip.render())
        assert "No daily history" not in strip_text


@pytest.mark.asyncio
async def test_modal_handles_zero_bars_without_crashing() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", [])
        await app.push_screen(screen)
        await pilot.pause()

        strip = screen.query_one(DailyChangeStrip)
        assert "No daily history available." in str(strip.render())


@pytest.mark.asyncio
async def test_close_button_dismisses() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars())
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.click("#stock-chart-close")
        await pilot.pause()

        assert not isinstance(app.screen, StockChartScreen)
