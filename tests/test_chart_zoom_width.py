"""Secondary-chart zoom default + candle width fitting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from textual.app import App, ComposeResult

from goldsilver.data.models import Bar
from goldsilver.data.settings import AppSettings
from goldsilver.widgets.chart import PriceChart


def test_secondary_chart_zoom_defaults_to_3h() -> None:
    assert AppSettings().chart_zoom2 == "3h"


def test_invalid_chart_zoom2_is_coerced() -> None:
    assert AppSettings(chart_zoom2="bogus").chart_zoom2 == "3h"  # type: ignore[arg-type]


def _candle_bars(n: int) -> list[Bar]:
    start = datetime(2026, 6, 9, 8, 0, tzinfo=timezone.utc)
    bars: list[Bar] = []
    for i in range(n):
        price = 2000.0 + i
        bars.append(
            Bar(
                symbol="XAU",
                time=start + timedelta(minutes=i),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price + 0.5,
                volume=0.0,
            )
        )
    return bars


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield PriceChart()


@pytest.mark.asyncio
async def test_candle_chart_reads_real_width() -> None:
    app = _Harness()
    async with app.run_test(size=(120, 40)) as pilot:
        chart = app.query_one(PriceChart)
        chart.seed(_candle_bars(180), kind="candle")
        chart.set_zoom("3h")
        await pilot.pause()
        width = chart.content_size.width
        target = chart._candle_target()

    assert width > 20
    assert target == max(20, width - 8)
