"""Mount-and-render tests for the gold/silver ratio mini tile."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult

from goldsilver.widgets.ratio_tile import RatioTile

_CSS = (
    Path(__file__).resolve().parents[1] / "src" / "goldsilver" / "styles" / "app.tcss"
)


class _Host(App[None]):
    CSS_PATH = str(_CSS)

    def compose(self) -> ComposeResult:
        yield RatioTile()


async def test_renders_ratio_with_change() -> None:
    app = _Host()
    async with app.run_test(size=(80, 10)) as pilot:
        tile = app.query_one(RatioTile)
        tile.apply_ratio(84.32, 84.0)
        await pilot.pause()
        text = str(tile.render())
        assert "Au/Ag" in text
        assert "84.3" in text
        assert "+0.38%" in text


async def test_extreme_zone_hint() -> None:
    app = _Host()
    async with app.run_test(size=(80, 10)) as pilot:
        tile = app.query_one(RatioTile)
        tile.apply_ratio(92.5, 92.0)
        await pilot.pause()
        assert "Ag cheap" in str(tile.render())
        tile.apply_ratio(68.0, 69.0)
        await pilot.pause()
        assert "Au cheap" in str(tile.render())
