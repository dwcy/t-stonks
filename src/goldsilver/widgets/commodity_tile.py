from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import CommodityQuote, CommoditySymbol


_LABEL: dict[CommoditySymbol, str] = {
    "BRENT": "Brent Oil",
    "COPPER": "Copper",
    "BTC": "Bitcoin",
}
_CURRENCY: dict[CommoditySymbol, str] = {
    "BRENT": "USD",
    "COPPER": "USD",
    "BTC": "USD",
}


class CommodityTile(Static):
    quote: reactive[CommodityQuote | None] = reactive(None)
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(self, symbol: CommoditySymbol) -> None:
        super().__init__("")
        self._symbol = symbol
        self.add_class("commodity-tile")

    def apply_quote(self, quote: CommodityQuote) -> None:
        self.stale_since = None
        self.quote = quote

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_quote(self, _: CommodityQuote | None) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        label = _LABEL.get(self._symbol, self._symbol)
        currency = _CURRENCY.get(self._symbol, "USD")
        if self.quote is None:
            self.update(Text(f"{label}  loading…", style="#7a7a8a"))
            return
        quote = self.quote
        change = quote.change
        pct = quote.change_percent
        flat = abs(change) < 0.001
        arrow = "▬" if flat else ("▲" if change > 0 else "▼")
        color = "#7a7a8a" if flat else ("#7dff8c" if change > 0 else "#ff6b6b")
        sign = "" if change < 0 else ("+" if not flat else " ")
        line = Text.assemble(
            (f"{label}  ", "#a0a0b0"),
            (f"{quote.price:.2f} ", "bold #e0e0e8"),
            (f"{currency}  ", "dim #7a7a8a"),
            (arrow, color),
            (f" {sign}{pct:.2f}%", color),
        )
        if self.stale_since is not None:
            local = self.stale_since.astimezone()
            line.append(f"  · stale {local.strftime('%H:%M')}", style="dim #ff6b6b")
        self.update(line)
