"""Mini tile for a central bank policy rate (USA Fed funds / Sweden Riksbank)."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import RatePoint, RateSource
from goldsilver.widgets.format import DOWN_COLOR, FLAT_COLOR, MUTED_COLOR, UP_COLOR

_LABEL: dict[RateSource, str] = {"fed": "Fed funds", "riksbank": "Riksbank"}
_NO_KEY_HINT: dict[RateSource, str] = {"fed": "set GOLDSILVER_FRED_KEY"}


class RateTile(Static):
    point: reactive[RatePoint | None] = reactive(None)

    def __init__(self, source: RateSource) -> None:
        super().__init__("")
        self._source = source
        self._no_key = False
        self.add_class("rate-tile")

    def apply_point(self, point: RatePoint | None) -> None:
        self._no_key = point is None and self._source in _NO_KEY_HINT
        self.point = point
        if point is None:
            self._redraw()

    def watch_point(self, _: RatePoint | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        label = _LABEL.get(self._source, self._source)
        if self.point is None:
            hint = _NO_KEY_HINT.get(self._source)
            text = f"{label} — {hint}" if self._no_key and hint else f"{label} loading…"
            self.update(Text(text, style=FLAT_COLOR))
            return
        point = self.point
        bp = (
            (point.value - point.previous) * 100.0
            if point.previous is not None
            else None
        )
        flat = bp is None or abs(bp) < 0.5
        arrow = "▬" if flat else ("▲" if bp > 0 else "▼")
        color = FLAT_COLOR if flat else (UP_COLOR if bp > 0 else DOWN_COLOR)
        line = Text.assemble(
            (f"{arrow} ", color),
            (f"{label} ", MUTED_COLOR),
            (f"{point.value:.2f}% ", "bold #e0e0e8"),
        )
        if bp is not None:
            sign = "+" if bp > 0 else ""
            line.append(f"{sign}{bp:.0f}bp", style=color)
        line.append(f"  {point.asof:%b %d}", style=f"dim {MUTED_COLOR}")
        self.update(line)
