from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import FxPair, FxRate


_PAIR_LABEL: dict[FxPair, str] = {
    "USDSEK": "USD/SEK",
    "CADSEK": "CAD/SEK",
}


class FxTile(Static):
    rate: reactive[FxRate | None] = reactive(None)
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(self, pair: FxPair) -> None:
        super().__init__("")
        self._pair = pair
        self.add_class("fx-tile")

    def apply_rate(self, rate: FxRate) -> None:
        self.stale_since = None
        self.rate = rate

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_rate(self, _: FxRate | None) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        label = _PAIR_LABEL[self._pair]
        if self.rate is None:
            self.update(Text(f"{label}  loading…", style="#7a7a8a"))
            return
        rate = self.rate
        change = rate.change
        pct = rate.change_percent
        flat = abs(change) < 0.0001
        arrow = "▬" if flat else ("▲" if change > 0 else "▼")
        color = "#7a7a8a" if flat else ("#7dff8c" if change > 0 else "#ff6b6b")
        sign = "" if change < 0 else ("+" if not flat else " ")
        line = Text.assemble(
            (f"{label}  ", "#a0a0b0"),
            (f"{rate.rate:.4f}  ", "bold #e0e0e8"),
            (arrow, color),
            (f" {sign}{pct:.2f}%", color),
            ("  (", color),
            (f"{sign}{change:.4f}", color),
            (")", color),
        )
        if self.stale_since is not None:
            local = self.stale_since.astimezone()
            line.append(f"  · stale {local.strftime('%H:%M')}", style="dim #ff6b6b")
        self.update(line)
