"""Mini tile for the 10Y TIPS real yield — colored from the gold perspective."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import RealYieldPoint
from goldsilver.widgets.format import DOWN_COLOR, FLAT_COLOR, MUTED_COLOR, UP_COLOR


class RealYieldTile(Static):
    point: reactive[RealYieldPoint | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__("")
        self._no_key = False
        self.add_class("yield-tile")

    def apply_point(self, point: RealYieldPoint | None) -> None:
        self._no_key = point is None
        self.point = point
        if point is None:
            self._redraw()

    def watch_point(self, _: RealYieldPoint | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        if self.point is None:
            if self._no_key:
                self.update(
                    Text("10Y real — set GOLDSILVER_FRED_KEY", style=FLAT_COLOR)
                )
            else:
                self.update(Text("10Y real loading…", style=FLAT_COLOR))
            return
        point = self.point
        bp = (
            (point.value - point.previous) * 100.0
            if point.previous is not None
            else None
        )
        flat = bp is None or abs(bp) < 0.5
        arrow = "▬" if flat else ("▲" if bp > 0 else "▼")
        # Gold perspective: rising real yields pressure gold, falling support it.
        color = FLAT_COLOR if flat else (DOWN_COLOR if bp > 0 else UP_COLOR)
        line = Text.assemble(
            (f"{arrow} ", color),
            ("10Y real ", MUTED_COLOR),
            (f"{point.value:.2f}% ", "bold #e0e0e8"),
        )
        if bp is not None:
            sign = "+" if bp > 0 else ""
            line.append(f"{sign}{bp:.0f}bp", style=color)
        line.append(f"  {point.asof:%b %d}", style=f"dim {MUTED_COLOR}")
        self.update(line)
