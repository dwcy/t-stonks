from __future__ import annotations

from datetime import datetime, timedelta, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static
from textual_plotext import PlotextPlot

from goldsilver.data.models_macro import StockQuote


class _StockSpark(PlotextPlot):
    DEFAULT_CSS = """
    _StockSpark {
        height: 4;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.theme = "clear"
        self._closes: tuple[float, ...] = ()
        self._color: tuple[int, int, int] = (160, 160, 180)

    def update_series(
        self, closes: tuple[float, ...], color: tuple[int, int, int]
    ) -> None:
        self._closes = closes
        self._color = color
        self._redraw()

    def on_mount(self) -> None:
        self._redraw()

    def _redraw(self) -> None:
        self.plt.clear_figure()
        if len(self._closes) >= 2:
            xs = list(range(len(self._closes)))
            self.plt.plot(xs, list(self._closes), color=self._color, marker="braille")
            self.plt.xticks([], [])
            self.plt.yticks([], [])
        self.refresh()


class StockTile(Vertical):
    quote: reactive[StockQuote | None] = reactive(None)
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(self, ticker: str) -> None:
        super().__init__()
        self.ticker = ticker
        self._first_seen_at = datetime.now(timezone.utc)
        self.add_class("stock-tile")

    def compose(self) -> ComposeResult:
        yield Static(self._render_header(), id="stock-head", classes="stock-head")
        yield _StockSpark()

    def apply_quote(self, quote: StockQuote) -> None:
        self.stale_since = None
        self.quote = quote

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_quote(self, _: StockQuote | None) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        try:
            head = self.query_one("#stock-head", Static)
            spark = self.query_one(_StockSpark)
        except Exception:
            return
        head.update(self._render_header())
        quote = self.quote
        if quote is None:
            spark.update_series((), (90, 90, 110))
            return
        change = quote.change
        if change > 0:
            color = (125, 255, 140)
        elif change < 0:
            color = (255, 107, 107)
        else:
            color = (160, 160, 180)
        spark.update_series(quote.intraday_closes, color)

    def _render_header(self) -> Text:
        if self.quote is None:
            age = datetime.now(timezone.utc) - self._first_seen_at
            if age > timedelta(seconds=30):
                return Text.assemble(
                    (f"{self.ticker:<8}", "bold #a0a0b0"),
                    ("  --", "dim #5a5a6a"),
                )
            return Text.assemble(
                (f"{self.ticker:<8}", "bold #a0a0b0"),
                ("  loading…", "dim #7a7a8a"),
            )
        quote = self.quote
        change = quote.change
        pct = quote.change_percent
        flat = abs(change) < 0.0001
        arrow = "▬" if flat else ("▲" if change > 0 else "▼")
        color = "#7a7a8a" if flat else ("#7dff8c" if change > 0 else "#ff6b6b")
        sign = "+" if change >= 0 else ""
        text = Text.assemble(
            (f"{quote.display_name:<8}", "bold #e0e0e8"),
            (f"{quote.price:>9.2f} ", "#e0e0e8"),
            (f"{quote.currency:<3} ", "dim #7a7a8a"),
            (arrow, color),
            (f" {sign}{pct:.2f}%", color),
        )
        if self.stale_since is not None:
            local = self.stale_since.astimezone()
            text.append(f"  · stale {local.strftime('%H:%M')}", style="dim #ff6b6b")
        return text
