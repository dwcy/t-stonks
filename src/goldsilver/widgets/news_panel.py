from __future__ import annotations

import webbrowser
from datetime import datetime, timezone

from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import NewsItem
from goldsilver.widgets.format import format_age


SOURCE_STYLE = {
    "REUTERS": "#ff6b6b",
    "BLOOMBERG": "#ff9b6b",
    "POLITICO": "#ffaa5a",
    "CNBC": "#7dcfff",
    "WllStrtJrnl": "#ffd56b",
    "YAHOO": "#c084fc",
    "FOX": "#ff5757",
    "DgnsIndstr": "#5dade2",
    "SVT": "#58d68d",
    "BREAKIT": "#26a69a",
    "Placera": "#aeea00",
    "AffrsVrldn": "#ffe082",
    "REDEYE": "#ff7043",
    "BrsKlln": "#42a5f5",
    "EFN": "#ffb74d",
    "TT": "#fecc00",
    "TRUMP": "#bb9af7",
    "WHITEHOUSE": "#e0e0e8",
    "IRNA": "#66bb6a",
    "MEHR": "#81c784",
}


def _has_openable_url(item: NewsItem) -> bool:
    return item.url.startswith(("http://", "https://"))


def render_news_row(text: Text, item: NewsItem, now: datetime) -> None:
    """Append one item's row (time · age · source · title) to a news `Text` block.

    The title span carries a "news_url" meta tag so a click can open the article —
    see NewsPanel.on_click / NewsLogScreen (same pattern as calendar_panel.py).
    """
    local = item.published.astimezone()
    delta = now - item.published
    age = format_age(int(delta.total_seconds()))
    time_str = local.strftime("%H:%M")
    if item.time_confidence == "approximate":
        time_str = f"~{time_str}"
    source_style = SOURCE_STYLE.get(item.source, "#7a7a8a")
    text.append(f"{time_str} ", style="#7a7a8a")
    text.append(f"{age:>7} ", style="dim #5a5a6a")
    text.append(f"{item.source:<11} ", style=source_style)
    title_start = len(text)
    text.append(f"{item.title}\n", style="#e0e0e8")
    if _has_openable_url(item):
        text.stylize(Style(meta={"news_url": item.url}), title_start, len(text) - 1)


class NewsBody(Static):
    """A news text block that opens the URL carried in the clicked span's meta."""

    def on_click(self, event: events.Click) -> None:
        style = event.style
        url = style.meta.get("news_url") if style is not None else None
        if url:
            webbrowser.open(url)
            event.stop()


class NewsPanel(VerticalScroll):
    items: reactive[tuple[NewsItem, ...]] = reactive(())
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(
        self,
        title: str = "Markets news",
        *,
        sources: tuple[str, ...] | None = None,
        per_source_cap: int = 5,
        total_cap: int = 80,
    ) -> None:
        super().__init__()
        self.border_title = title
        self._sources_filter = sources
        self._per_source_cap = per_source_cap
        self._total_cap = total_cap
        self._by_source: dict[str, list[NewsItem]] = {}

    def compose(self) -> ComposeResult:
        yield NewsBody("loading…", id="news-body")

    def replace_items(self, items: list[NewsItem]) -> None:
        self._by_source.clear()
        self.apply_items(items)

    def apply_items(self, items: list[NewsItem]) -> None:
        self.stale_since = None
        if self._sources_filter is not None:
            items = [i for i in items if i.source in self._sources_filter]
        touched_sources = {i.source for i in items}
        for src in touched_sources:
            src_items = sorted(
                [i for i in items if i.source == src],
                key=lambda i: i.published,
                reverse=True,
            )
            self._by_source[src] = src_items[: self._per_source_cap]
        merged: list[NewsItem] = []
        for src_items in self._by_source.values():
            merged.extend(src_items)
        merged.sort(key=lambda i: i.published, reverse=True)
        self.items = tuple(merged[: self._total_cap])

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_items(self, _: tuple[NewsItem, ...]) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        body = self.query_one("#news-body", NewsBody)
        if not self.items:
            body.update(Text("loading…", style="#7a7a8a"))
            self.border_subtitle = ""
            return
        text = Text()
        now = datetime.now(timezone.utc)
        for item in self.items:
            render_news_row(text, item, now)
        body.update(text)
        latest = max(i.published for i in self.items)
        marker = f"latest {latest.astimezone().strftime('%H:%M')}"
        if self.stale_since is not None:
            marker = f"stale since {self.stale_since.astimezone().strftime('%H:%M')}"
        self.border_subtitle = marker
