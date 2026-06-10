"""Always-visible pre-open index-futures row: US live + labeled EU cash proxies."""

from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_futures import FuturesSnapshot, FutureQuote

_UP = "#7dff8c"
_DOWN = "#ff6b6b"
_FLAT = "#7a7a8a"
_LABEL = "#a0a0b0"
_DIM = "#5a5a6a"


def _direction(change: float, *, eps: float) -> tuple[str, str]:
    if abs(change) < eps:
        return "▬", _FLAT
    if change > 0:
        return "▲", _UP
    return "▼", _DOWN


class FuturesStrip(Static):
    snapshot: reactive[FuturesSnapshot | None] = reactive(None)
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__("")
        self.add_class("futures-strip")

    def apply_snapshot(self, snapshot: FuturesSnapshot) -> None:
        self.stale_since = None
        self.snapshot = snapshot

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_snapshot(self, _: FuturesSnapshot | None) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        snap = self.snapshot
        text = Text()
        text.append("TERMINER ", style="bold #a0a0b0")
        text.append("≈ ", style=_DIM)
        if snap is None:
            text.append(" loading…", style=_FLAT)
            self.update(text)
            return

        live = [q for q in snap.quotes if q.is_live]
        cash = [q for q in snap.quotes if not q.is_live]
        for q in live:
            self._append_quote(text, q, dim=False)
        if cash:
            text.append("  ·  cash(igår): ", style=_DIM)
            for q in cash:
                self._append_quote(text, q, dim=True)

        if self.stale_since is not None:
            local = self.stale_since.astimezone()
            text.append(f" · stale {local.strftime('%H:%M')}", style="dim #ff6b6b")
        self.update(text)

    @staticmethod
    def _append_quote(text: Text, q: FutureQuote, *, dim: bool) -> None:
        label_style = f"dim {_LABEL}" if dim else _LABEL
        text.append(f"{q.label} ", style=label_style)
        if q.kind == "vol":
            arrow, color = _direction(q.change, eps=0.01)
            value = f"{q.price:.2f} {arrow}"
        elif q.kind == "rate":
            arrow, color = _direction(q.change, eps=0.001)
            value = f"{q.price:.2f}% {arrow}"
        else:
            arrow, color = _direction(q.change_percent, eps=0.005)
            sign = "+" if q.change_percent >= 0 else ""
            value = f"{sign}{q.change_percent:.2f}% {arrow}"
        text.append(f"{value}  ", style=f"dim {color}" if dim else color)
