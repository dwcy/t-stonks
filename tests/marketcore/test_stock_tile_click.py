"""Clicking a stock tile's mini sparkline requests its full detail chart."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from marketcore.widgets.stock_tile import StockTile


class _StubClick:
    def stop(self) -> None:
        pass


class _Harness(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.requested: list[str] = []

    def compose(self) -> ComposeResult:
        yield StockTile("NVDA", on_chart_requested=self.requested.append)


@pytest.mark.asyncio
async def test_clicking_spark_requests_chart_for_ticker() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        from marketcore.widgets.stock_tile import _StockSpark

        spark = app.query_one(_StockSpark)
        spark.on_click(_StubClick())  # type: ignore[arg-type]
        await pilot.pause()

    assert app.requested == ["NVDA"]


@pytest.mark.asyncio
async def test_no_callback_does_not_raise_on_click() -> None:
    class _NoCallbackHarness(App[None]):
        def compose(self) -> ComposeResult:
            yield StockTile("NVDA")

    app = _NoCallbackHarness()
    async with app.run_test() as pilot:
        from marketcore.widgets.stock_tile import _StockSpark

        spark = app.query_one(_StockSpark)
        spark.on_click(_StubClick())  # type: ignore[arg-type]
        await pilot.pause()
