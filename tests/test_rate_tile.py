"""Mount-and-render tests for the central bank policy rate mini tile."""

from __future__ import annotations

from datetime import date

from textual.app import App, ComposeResult

from goldsilver.data.models_macro import RatePoint
from goldsilver.widgets.rate_tile import RateTile


class _Host(App[None]):
    def __init__(self, source: str) -> None:
        super().__init__()
        self._source = source

    def compose(self) -> ComposeResult:
        yield RateTile(self._source)  # type: ignore[arg-type]


async def test_renders_fed_rate_with_change() -> None:
    app = _Host("fed")
    async with app.run_test() as pilot:
        tile = app.query_one(RateTile)
        tile.apply_point(
            RatePoint(value=5.33, previous=5.08, asof=date(2026, 6, 9), source="fed")
        )
        await pilot.pause()
        text = str(tile.render())

    assert "Fed funds" in text
    assert "5.33%" in text
    assert "+25bp" in text


async def test_fed_no_key_shows_hint() -> None:
    app = _Host("fed")
    async with app.run_test() as pilot:
        tile = app.query_one(RateTile)
        tile.apply_point(None)
        await pilot.pause()
        text = str(tile.render())

    assert "GOLDSILVER_FRED_KEY" in text


async def test_renders_riksbank_rate() -> None:
    app = _Host("riksbank")
    async with app.run_test() as pilot:
        tile = app.query_one(RateTile)
        tile.apply_point(
            RatePoint(
                value=1.75, previous=2.0, asof=date(2026, 7, 10), source="riksbank"
            )
        )
        await pilot.pause()
        text = str(tile.render())

    assert "Riksbank" in text
    assert "1.75%" in text
    assert "-25bp" in text
