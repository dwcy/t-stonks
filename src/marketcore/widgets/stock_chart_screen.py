"""Modal showing a stock tile's full detail chart + 40-day up/down history strip.

Lives in marketcore (not goldsilver/widgets) so both goldsilver and quantum can
open it directly from their own StockTile instances without a cross-app import.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from marketcore.models import Bar
from marketcore.widgets.chart import PriceChart
from marketcore.widgets.daily_change_strip import (
    DailyChangeStrip,
    compute_daily_changes,
)


class StockChartScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, ticker: str, bars: list[Bar]) -> None:
        super().__init__()
        self._ticker = ticker
        self._bars = bars

    def compose(self) -> ComposeResult:
        with Container(id="stock-chart-dialog"):
            yield Static(self._ticker, id="stock-chart-title")
            yield PriceChart(color="white")
            yield DailyChangeStrip()
            yield Button("Close", id="stock-chart-close")

    def on_mount(self) -> None:
        self.query_one(PriceChart).seed(self._bars, kind="line")
        self.query_one(DailyChangeStrip).apply_changes(
            compute_daily_changes(self._bars)
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stock-chart-close":
            self.dismiss()
