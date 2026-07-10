"""Mount-and-render tests for the international index mini tile."""

from __future__ import annotations

from datetime import datetime, timezone

from textual.app import App, ComposeResult

from goldsilver.data.models_macro import IndexPoint
from goldsilver.widgets.index_tile import IndexTile


class _Host(App[None]):
    def __init__(self, symbol: str) -> None:
        super().__init__()
        self._symbol = symbol

    def compose(self) -> ComposeResult:
        yield IndexTile(self._symbol)  # type: ignore[arg-type]


async def test_renders_open_index_with_change() -> None:
    app = _Host("DAX")
    async with app.run_test() as pilot:
        tile = app.query_one(IndexTile)
        tile.apply_point(
            IndexPoint(
                symbol="DAX",
                level=24000.0,
                previous_close=23800.0,
                session_open=True,
                time=datetime.now(timezone.utc),
            )
        )
        await pilot.pause()
        text = str(tile.render())

    assert "DAX" in text
    assert "24,000" in text
    assert "closed" not in text


async def test_renders_closed_marker_outside_session() -> None:
    app = _Host("NIKKEI225")
    async with app.run_test() as pilot:
        tile = app.query_one(IndexTile)
        tile.apply_point(
            IndexPoint(
                symbol="NIKKEI225",
                level=39000.0,
                previous_close=39500.0,
                session_open=False,
                time=datetime.now(timezone.utc),
            )
        )
        await pilot.pause()
        text = str(tile.render())

    assert "Nikkei 225" in text
    assert "closed" in text
