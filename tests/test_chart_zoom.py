"""Click inside a live chart cycles the zoom level (replacing scroll-to-zoom)."""

from __future__ import annotations

from textual.app import App, ComposeResult

from goldsilver.widgets.chart import PriceChart


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield PriceChart(color="white")


async def test_click_cycles_zoom_wrapping() -> None:
    app = _Host()
    async with app.run_test(size=(80, 24)) as pilot:
        chart = app.query_one(PriceChart)
        assert chart.zoom == "24h"
        await pilot.click(PriceChart)
        assert chart.zoom == "3h"
        await pilot.click(PriceChart)
        assert chart.zoom == "1h"
        await pilot.click(PriceChart)
        assert chart.zoom == "24h"  # wraps back to widest


async def test_click_ignored_in_history_mode() -> None:
    app = _Host()
    async with app.run_test(size=(80, 24)) as pilot:
        chart = app.query_one(PriceChart)
        chart.set_mode("history")
        await pilot.click(PriceChart)
        assert chart.zoom == "24h"  # unchanged
