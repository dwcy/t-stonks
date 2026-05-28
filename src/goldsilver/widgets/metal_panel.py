from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models import Bar, Tick
from goldsilver.widgets.chart import PriceChart


def _rgb(color: tuple[int, int, int] | str) -> str:
    if isinstance(color, str):
        return color
    r, g, b = color
    return f"rgb({r},{g},{b})"


class MetalPanel(Vertical):
    price: reactive[float | None] = reactive(None)
    change: reactive[float] = reactive(0.0)
    change_percent: reactive[float] = reactive(0.0)
    day_high: reactive[float] = reactive(0.0)
    day_low: reactive[float] = reactive(0.0)
    updated_at: reactive[datetime | None] = reactive(None)

    def __init__(
        self,
        symbol: str,
        label: str,
        *,
        accent_color: tuple[int, int, int] | str = "white",
        classes: str = "",
    ) -> None:
        super().__init__(classes=classes)
        self.symbol = symbol
        self._accent = _rgb(accent_color)
        self.border_title = label

    def compose(self) -> ComposeResult:
        yield Static("--:--:--", id="updated", classes="updated")
        yield Static(self._render_header(), id="header", classes="header")
        yield Static("", id="change-row", classes="change-row")
        yield PriceChart(color=self._accent_rgb_tuple())

    def _accent_rgb_tuple(self) -> tuple[int, int, int] | str:
        if self._accent.startswith("rgb("):
            inner = self._accent[4:-1]
            r, g, b = (int(x) for x in inner.split(","))
            return (r, g, b)
        return self._accent

    def seed_history(
        self, bars: list[Bar], *, x_origin: datetime | None = None
    ) -> None:
        self.query_one(PriceChart).seed(bars, x_origin=x_origin)

    def apply_tick(self, tick: Tick) -> None:
        self.price = tick.price
        self.change = tick.change
        self.change_percent = tick.change_percent
        self.day_high = tick.day_high
        self.day_low = tick.day_low
        self.updated_at = tick.time
        chart = self.query_one(PriceChart)
        chart.add_point(tick.price, tick.time)

    def watch_price(self, _: float | None) -> None:
        self._refresh_header()
        self._refresh_change_row()

    def watch_change(self, _: float) -> None:
        self._refresh_change_row()

    def watch_change_percent(self, _: float) -> None:
        self._refresh_change_row()

    def watch_day_high(self, _: float) -> None:
        self._refresh_header()

    def watch_day_low(self, _: float) -> None:
        self._refresh_header()

    def watch_updated_at(self, ts: datetime | None) -> None:
        widget = self.query_one_optional("#updated", Static)
        if widget is None:
            return
        if ts is None:
            widget.update(Text("--:--:--", style="dim #5a5a6a"))
            return
        local = ts.astimezone()
        widget.update(
            Text(local.strftime("%H:%M:%S"), style="dim #7a7a8a")
        )

    def _render_header(self) -> Text:
        if self.price is None:
            return Text("waiting…", style="dim #7a7a8a")
        parts: list[tuple[str, str]] = [
            (f"{self.price:,.2f}", f"bold {self._accent}"),
        ]
        if self.day_high != 0.0 or self.day_low != 0.0:
            parts.extend([
                ("   ", ""),
                ("H ", "#7a7a8a"),
                (f"{self.day_high:,.2f}", "#7dff8c"),
                ("   ", ""),
                ("L ", "#7a7a8a"),
                (f"{self.day_low:,.2f}", "#ff6b6b"),
            ])
        return Text.assemble(*parts)

    def _render_change_row(self) -> Text:
        if self.price is None:
            return Text("")
        change_style = "#7dff8c" if self.change >= 0 else "#ff6b6b"
        arrow = "▲" if self.change >= 0 else "▼"
        sign = "+" if self.change >= 0 else ""
        return Text.assemble(
            (arrow, change_style),
            (f" {sign}{self.change_percent:.2f}%", change_style),
            ("  (", change_style),
            (f"{sign}{self.change:.2f}", change_style),
            (")", change_style),
        )

    def _refresh_header(self) -> None:
        widget = self.query_one_optional("#header", Static)
        if widget is not None:
            widget.update(self._render_header())

    def _refresh_change_row(self) -> None:
        widget = self.query_one_optional("#change-row", Static)
        if widget is not None:
            widget.update(self._render_change_row())
