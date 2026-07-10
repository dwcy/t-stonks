"""Modal browsing the news feed's retained history beyond the live panel's window."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from goldsilver.data.models_macro import NewsItem
from goldsilver.widgets.news_panel import NewsBody, render_news_row


class NewsLogScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, items: tuple[NewsItem, ...]) -> None:
        super().__init__()
        self._items = items

    def compose(self) -> ComposeResult:
        with Container(id="news-log-dialog"):
            yield Static("News log", id="news-log-title")
            with VerticalScroll(id="news-log-body"):
                yield NewsBody(self._build_text(), id="news-log-text")
            yield Button("Close", id="news-log-close")

    def _build_text(self) -> Text:
        text = Text()
        if not self._items:
            text.append("No history yet.", style="#7a7a8a")
            return text
        now = datetime.now(timezone.utc)
        for item in self._items:
            render_news_row(text, item, now)
        return text

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "news-log-close":
            self.dismiss()
