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


class StockChartScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        ticker: str,
        bars: list[Bar],
        *,
        next_report_at: datetime | None = None,
        latest_report_summary: str | None = None,
        latest_report_path: str | None = None,
        dividend: DividendInfo | None = None,
    ) -> None:
        super().__init__()
        self._ticker = ticker
        self._bars = bars
        self._next_report_at = next_report_at
        self._latest_report_summary = latest_report_summary
        self._latest_report_path = latest_report_path
        self._dividend = dividend

    def compose(self) -> ComposeResult:
        with Container(id="stock-chart-dialog"):
            yield Static(self._ticker, id="stock-chart-title")
            yield PriceChart(color="white")
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
        self.query_one(PriceChart).seed(self._bars, kind="line")
        self.query_one(DailyChangeStrip).apply_changes(
            compute_daily_changes(self._bars)
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stock-chart-close":
            self.dismiss()
        elif event.button.id == "stock-chart-open-report" and self._latest_report_path:
            webbrowser.open(self._latest_report_path)
