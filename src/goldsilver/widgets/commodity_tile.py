from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import CommodityQuote, CommoditySymbol
from goldsilver.widgets.format import DOWN_COLOR, FLAT_COLOR, MUTED_COLOR, UP_COLOR


_LABEL: dict[CommoditySymbol, str] = {
    "BRENT": "Oil",
    "COPPER": "Copper",
    "BTC": "BTC",
    "DXY": "Dollar Index",
}
_CURRENCY: dict[CommoditySymbol, str] = {
    "BRENT": "USD",
    "COPPER": "USD",
    "BTC": "USD",
    "DXY": "USD",
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
        if self.quote is None:
            self.update(Text(f"{label} loading…", style=FLAT_COLOR))
            return
        quote = self.quote
        change = quote.change
        pct = quote.change_percent
        flat = abs(change) < 0.001
        arrow = "▬" if flat else ("▲" if change > 0 else "▼")
        color = FLAT_COLOR if flat else (UP_COLOR if change > 0 else DOWN_COLOR)
        sign = "" if change < 0 else ("+" if not flat else " ")
        price_str = (
            f"{quote.price:,.0f}" if quote.price >= 1000 else f"{quote.price:.2f}"
        )
        line = Text.assemble(
            (f"{arrow} ", color),
            (f"{label} ", MUTED_COLOR),
            (f"{sign}{pct:.2f}% ", color),
            (price_str, "bold #e0e0e8"),
        )
        if self.stale_since is not None:
            local = self.stale_since.astimezone()
            line.append(
                f"  · stale {local.strftime('%H:%M')}", style=f"dim {DOWN_COLOR}"
            )
        self.update(line)
