"""Mini tile showing the live gold/silver ratio with historical-extreme hints."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.widgets.format import DOWN_COLOR, FLAT_COLOR, MUTED_COLOR, UP_COLOR

# Historically the ratio mean-reverts from these zones: above ~90 silver is
# cheap relative to gold; below ~70 gold is cheap relative to silver.
RATIO_HIGH_EXTREME = 90.0
RATIO_LOW_EXTREME = 70.0


class RatioTile(Static):
    ratio: reactive[float | None] = reactive(None)
    prev_ratio: reactive[float | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__("")
        self.add_class("ratio-tile")

    def apply_ratio(self, ratio: float, prev_ratio: float | None) -> None:
        self.prev_ratio = prev_ratio
        self.ratio = ratio

    def watch_ratio(self, _: float | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        if self.ratio is None:
            self.update(Text("Gold/Silver Ratio loading…", style=FLAT_COLOR))
            return
        ratio = self.ratio
        if self.prev_ratio:
            pct = (ratio - self.prev_ratio) / self.prev_ratio * 100.0
        else:
            pct = 0.0
        flat = abs(pct) < 0.01
        arrow = "▬" if flat else ("▲" if pct > 0 else "▼")
        color = FLAT_COLOR if flat else (UP_COLOR if pct > 0 else DOWN_COLOR)
        sign = "+" if pct > 0 else ""
        line = Text.assemble(
            (f"{arrow} ", color),
            ("Gold/Silver Ratio ", MUTED_COLOR),
            (f"{ratio:.1f} ", "bold #e0e0e8"),
            (f"{sign}{pct:.2f}%", color),
        )
        if ratio >= RATIO_HIGH_EXTREME:
            line.append("  · Silver cheap", style=f"bold {UP_COLOR}")
        elif ratio <= RATIO_LOW_EXTREME:
            line.append("  · Gold cheap", style=f"bold {UP_COLOR}")
        self.update(line)
