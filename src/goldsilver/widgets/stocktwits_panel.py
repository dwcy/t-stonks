from __future__ import annotations

import re
from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import StockTwitMessage
from goldsilver.widgets.format import format_age


_TICKER_TAG_RE = re.compile(r"^(?:\$[A-Z][A-Z0-9._]*\s+)+")
_WHITESPACE_RE = re.compile(r"\s+")


def _clean_body(body: str) -> str:
    cleaned = _TICKER_TAG_RE.sub("", body, count=1)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


class StockTwitsPanel(VerticalScroll):
    messages: reactive[tuple[StockTwitMessage, ...]] = reactive(())
    stale_since: reactive[datetime | None] = reactive(None)

    def __init__(
        self,
        title: str = "StockTwits — DJT / GLD / SLV",
        *,
        max_messages: int = 40,
        body_chars: int = 110,
    ) -> None:
        super().__init__()
        self.border_title = title
        self._max_messages = max_messages
        self._body_chars = body_chars

    def compose(self) -> ComposeResult:
        yield Static("loading…", id="stocktwits-body")

    def replace_messages(self, messages: list[StockTwitMessage]) -> None:
        self.stale_since = None
        self.messages = tuple(messages[: self._max_messages])

    def mark_stale(self, since: datetime) -> None:
        self.stale_since = since

    def watch_messages(self, _: tuple[StockTwitMessage, ...]) -> None:
        self._redraw()

    def watch_stale_since(self, _: datetime | None) -> None:
        self._redraw()

    def _redraw(self) -> None:
        body = self.query_one("#stocktwits-body", Static)
        if not self.messages:
            body.update(Text("loading…", style="#7a7a8a"))
            self.border_subtitle = ""
            return
        text = Text()
        bull = sum(1 for m in self.messages if m.sentiment == "BULL")
        bear = sum(1 for m in self.messages if m.sentiment == "BEAR")
        text.append(f"{len(self.messages)} posts  ", style="#a0a0b0")
        text.append(f"{bull} bull", style="bold #7dff8c")
        text.append(" · ", style="#3a3a4a")
        text.append(f"{bear} bear", style="bold #ff6b6b")
        text.append("\n", style="")
        now = datetime.now(timezone.utc)
        for msg in self.messages:
            self._render_message(text, msg, now)
        body.update(text)
        if self.stale_since is not None:
            local = self.stale_since.astimezone().strftime("%H:%M")
            self.border_subtitle = f"stale since {local}"
        else:
            latest = max(m.created_at for m in self.messages).astimezone()
            self.border_subtitle = f"latest {latest.strftime('%H:%M')}"

    def _render_message(self, text: Text, msg: StockTwitMessage, now: datetime) -> None:
        age = format_age(int((now - msg.created_at).total_seconds()))
        sentiment_style = (
            "bold #7dff8c"
            if msg.sentiment == "BULL"
            else "bold #ff6b6b"
            if msg.sentiment == "BEAR"
            else "dim #5a5a6a"
        )
        sentiment_label = (
            "▲" if msg.sentiment == "BULL" else "▼" if msg.sentiment == "BEAR" else "·"
        )
        body_clean = _clean_body(msg.body)
        if len(body_clean) > self._body_chars:
            body_clean = body_clean[: self._body_chars - 1].rstrip() + "…"
        text.append(f"{age:>6} ", style="dim #5a5a6a")
        text.append(f"{sentiment_label} ", style=sentiment_style)
        text.append(f"${msg.source_ticker:<5}", style="#ffd56b")
        text.append(f" @{msg.user_username:<16} ", style="#c084fc")
        text.append(body_clean, style="#e0e0e8")
        text.append("\n", style="")
