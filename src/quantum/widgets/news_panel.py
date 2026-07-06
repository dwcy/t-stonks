"""QuantumNewsPanel — scrolling list of quantum-computing headlines."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.widgets import Static

from marketcore.models_macro import NewsItem
from marketcore.widgets.format import MUTED_COLOR, format_age

MAX_ROWS = 40


class QuantumNewsPanel(Static):
    def __init__(self) -> None:
        super().__init__(id="news-panel")
        self._items: tuple[NewsItem, ...] = ()
        self._stale_since: datetime | None = None

    def apply_items(self, items: list[NewsItem]) -> None:
        self._stale_since = None
        self._items = tuple(items[:MAX_ROWS])
        self.update(self._build_text())

    def mark_stale(self, since: datetime) -> None:
        self._stale_since = since
        self.update(self._build_text())

    def _build_text(self) -> Text:
        if not self._items:
            note = "no headlines yet…"
            if self._stale_since is not None:
                note = "news feed unavailable"
            return Text(note, style=f"dim {MUTED_COLOR}")
        now = datetime.now(timezone.utc)
        text = Text()
        for item in self._items:
            local = item.published.astimezone()
            age = int((now - item.published).total_seconds())
            text.append(f"{local.strftime('%m-%d %H:%M')} ", style="#7a7a8a")
            text.append(f"{format_age(age):>5} ", style=f"dim {MUTED_COLOR}")
            text.append(f"{item.source:<11} ", style=f"bold {MUTED_COLOR}")
            text.append(f"{item.title}\n", style="#e0e0e8")
        return text
