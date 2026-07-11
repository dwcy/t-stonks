"""Mini tile for a national equity index (DAX/CAC 40/FTSE 100/Nikkei 225)."""

from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import IndexPoint, IndexSymbol
from goldsilver.widgets.format import DOWN_COLOR, FLAT_COLOR, MUTED_COLOR, UP_COLOR

_LABEL: dict[IndexSymbol, str] = {
    "DAX": "DAX",
    "CAC40": "CAC 40",
    "FTSE100": "FTSE 100",
    "NIKKEI225": "Nikkei 225",
}


class IndexTile(Static):
    point: reactive[IndexPoint | None] = reactive(None)
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(self, symbol: IndexSymbol) -> None:
        super().__init__("")
        self._symbol = symbol
        self.add_class("index-tile")

    def apply_point(self, point: IndexPoint) -> None:
        self.stale_since = None
        self.point = point

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_point(self, _: IndexPoint | None) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        label = _LABEL.get(self._symbol, self._symbol)
        if self.point is None:
            self.update(Text(f"{label} loading…", style=FLAT_COLOR))
            return
        point = self.point
        change = point.change
        pct = point.change_percent
        flat = abs(change) < 0.001
        arrow = "▬" if flat else ("▲" if change > 0 else "▼")
        color = FLAT_COLOR if flat else (UP_COLOR if change > 0 else DOWN_COLOR)
        sign = "" if change < 0 else ("+" if not flat else " ")
        level_str = (
            f"{point.level:,.0f}" if point.level >= 1000 else f"{point.level:.2f}"
        )
        line = Text.assemble(
            (f"{arrow} ", color),
            (f"{label} ", MUTED_COLOR),
            (f"{sign}{pct:.2f}% ", color),
            (level_str, "bold #e0e0e8"),
        )
        if not point.session_open:
            line.append("  · closed", style=f"dim {MUTED_COLOR}")
        if self.stale_since is not None:
            local = self.stale_since.astimezone()
            line.append(
                f"  · stale {local.strftime('%H:%M')}", style=f"dim {DOWN_COLOR}"
            )
        self.update(line)
