"""Modal showing a stock tile's full detail chart, 40-day strip, report status, and dividend.

Lives in marketcore (not goldsilver/widgets) so both goldsilver and quantum can
open it directly from their own StockTile instances without a cross-app import.
Report status is passed in as caller-formatted strings (not a goldsilver
ReportRun object) so this module stays symbol/app-agnostic — only goldsilver's
report engine exists today, quantum has none, so the report section is simply
omitted when the caller (goldsilver's app.py) has nothing to pass.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from marketcore.models import Bar
from marketcore.models_macro import DividendInfo
from marketcore.widgets.chart import PriceChart
from marketcore.widgets.daily_change_strip import (
    DailyChangeStrip,
    compute_daily_changes,
)

DEFAULT_ACCENT_COLOR = "#8ab4ff"
ERROR_MESSAGE = "Couldn't load chart data — press r to retry."


class StockChartScreen(ModalScreen[None]):
    # Textual's App.AUTO_FOCUS defaults to "*", which would auto-focus the
    # "Close" button and make it swallow "enter" (pin) as a button press.
    AUTO_FOCUS = ""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("z", "cycle_zoom", "Zoom"),
        ("h", "cycle_mode", "Mode"),
        ("x", "toggle_crosshair", "Crosshair"),
        ("left", "crosshair_left", "← cursor"),
        ("right", "crosshair_right", "cursor →"),
        ("pageup", "crosshair_page_left", "←← cursor"),
        ("pagedown", "crosshair_page_right", "cursor →→"),
        ("enter", "pin_current", "Pin"),
        ("c", "clear_pins", "Clear pins"),
        ("r", "retry", "Retry"),
    ]

    def __init__(
        self,
        ticker: str,
        bars: list[Bar],
        *,
        next_report_at: datetime | None = None,
        latest_report_summary: str | None = None,
        latest_report_path: str | None = None,
        dividend: DividendInfo | None = None,
        accent_color: tuple[int, int, int] | str = DEFAULT_ACCENT_COLOR,
        on_retry: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._ticker = ticker
        self._bars = bars
        self._next_report_at = next_report_at
        self._latest_report_summary = latest_report_summary
        self._latest_report_path = latest_report_path
        self._dividend = dividend
        self._accent_color = accent_color
        self._on_retry = on_retry

    def compose(self) -> ComposeResult:
        with Container(id="stock-chart-dialog"):
            yield Static(self._ticker, id="stock-chart-title")
            if not self._bars:
                yield Static(ERROR_MESSAGE, id="stock-chart-error")
            yield PriceChart(color=self._accent_color)
            yield DailyChangeStrip()
            if self._show_report_section:
                yield Static(self._build_report_text(), id="stock-chart-report")
                if self._latest_report_path:
                    yield Button("Open latest report", id="stock-chart-open-report")
            yield Static(self._build_dividend_text(), id="stock-chart-dividend")
            yield Button("Close", id="stock-chart-close")

    @property
    def _show_report_section(self) -> bool:
        return (
            self._next_report_at is not None or self._latest_report_summary is not None
        )

    def _build_report_text(self) -> str:
        lines: list[str] = []
        if self._next_report_at is not None:
            lines.append(f"Next report: {self._next_report_at.strftime('%H:%M')}")
        if self._latest_report_summary is not None:
            lines.append(f"Latest report: {self._latest_report_summary}")
        return "\n".join(lines)

    def _build_dividend_text(self) -> str:
        dividend = self._dividend
        if dividend is None or dividend.amount is None or dividend.payment_date is None:
            return "Dividend: no dividend information available"
        label = "Next payment" if dividend.is_forward_looking else "Last payment"
        return (
            f"{label}: {dividend.payment_date.isoformat()}  {dividend.amount:.4f}/share"
        )

    def on_mount(self) -> None:
        self._seed_chart()
        self.query_one(DailyChangeStrip).apply_changes(
            compute_daily_changes(self._bars)
        )

    def _seed_chart(self) -> None:
        chart = self.query_one(PriceChart)
        bars = self._bars
        show_day_refs = len(bars) >= 2
        chart.seed(
            bars,
            kind="line",
            show_sma=True,
            show_vwap=True,
            show_day_refs=show_day_refs,
        )
        if show_day_refs:
            chart.apply_session_refs(bars[-2].close, bars[-1].high, bars[-1].low)
        chart.set_mode("history")

    def apply_bars(self, bars: list[Bar]) -> None:
        """Re-seed after a retry-triggered refetch, swapping the error message out."""
        self._bars = bars
        error = self.query_one_optional("#stock-chart-error", Static)
        if bars:
            if error is not None:
                error.remove()
        elif error is None:
            self.query_one("#stock-chart-dialog", Container).mount(
                Static(ERROR_MESSAGE, id="stock-chart-error"),
                before=self.query_one(PriceChart),
            )
        self._seed_chart()
        self.query_one(DailyChangeStrip).apply_changes(compute_daily_changes(bars))

    def action_cycle_zoom(self) -> None:
        self.query_one(PriceChart).cycle_zoom()

    def action_cycle_mode(self) -> None:
        self.query_one(PriceChart).cycle_mode()

    def action_toggle_crosshair(self) -> None:
        self.query_one(PriceChart).toggle_crosshair()

    def action_crosshair_left(self) -> None:
        self.query_one(PriceChart).move_crosshair(-1)

    def action_crosshair_right(self) -> None:
        self.query_one(PriceChart).move_crosshair(1)

    def action_crosshair_page_left(self) -> None:
        self.query_one(PriceChart).move_crosshair(-60)

    def action_crosshair_page_right(self) -> None:
        self.query_one(PriceChart).move_crosshair(60)

    def action_pin_current(self) -> None:
        self.query_one(PriceChart).pin_current()

    def action_clear_pins(self) -> None:
        self.query_one(PriceChart).clear_pins()

    def action_retry(self) -> None:
        if self._on_retry is not None:
            self._on_retry()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stock-chart-close":
            self.dismiss()
        elif event.button.id == "stock-chart-open-report" and self._latest_report_path:
            webbrowser.open(self._latest_report_path)
