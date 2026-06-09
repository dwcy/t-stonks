"""Modal detail view for a single macro calendar event with on-demand actuals fetch."""

from __future__ import annotations

from collections.abc import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from goldsilver.data.models_macro import CalendarEvent
from goldsilver.data.session import STOCKHOLM

_IMPACT_STYLE = {
    "HIGH": "bold #ff6b6b",
    "MED": "#ffd56b",
    "LOW": "#6a6a78",
}
_SOURCE_STYLE = {
    "FED": "#7dcfff",
    "ECB": "#bb9af7",
    "RIKSBANK": "#ffd56b",
}
_LABEL_STYLE = "#7a7a8a"
_VALUE_STYLE = "#e0e0e8"
_RELEASED_STYLE = "#7dff8c"


class CalendarEventScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        event: CalendarEvent,
        *,
        on_fetch: Callable[[], None] | None = None,
        can_fetch: bool = False,
    ) -> None:
        super().__init__()
        self._event = event
        self._on_fetch = on_fetch
        self._can_fetch = can_fetch

    def compose(self) -> ComposeResult:
        with Container(id="cal-event-dialog"):
            yield Static(self._event.title, id="cal-event-title")
            yield Static(self._build_meta(), id="cal-event-meta")
            yield Static(self._build_figures(), id="cal-event-figures")
            yield Static("", id="cal-event-status")
            with Horizontal(id="cal-event-actions"):
                if self._can_fetch:
                    yield Button("Fetch now", id="cal-event-fetch", variant="primary")
                yield Button("Close", id="cal-event-close")

    def _build_meta(self) -> Text:
        event = self._event
        text = Text()
        text.append("Source    ", style=_LABEL_STYLE)
        text.append(
            f"{event.source}\n", style=_SOURCE_STYLE.get(event.source, _VALUE_STYLE)
        )
        text.append("Impact    ", style=_LABEL_STYLE)
        importance = event.importance or "—"
        text.append(
            f"{importance}\n",
            style=_IMPACT_STYLE.get(event.importance or "", _VALUE_STYLE),
        )
        text.append("Scheduled ", style=_LABEL_STYLE)
        if event.all_day:
            when = event.scheduled_time.astimezone(STOCKHOLM).strftime(
                "%a %d %b (all day)"
            )
        else:
            when = event.scheduled_time.astimezone(STOCKHOLM).strftime("%a %d %b %H:%M")
        text.append(f"{when}\n", style=_VALUE_STYLE)
        text.append("Status    ", style=_LABEL_STYLE)
        text.append(event.status, style=_VALUE_STYLE)
        return text

    def _build_figures(self) -> Text:
        event = self._event
        text = Text()
        has_data = event.status == "RELEASED" or event.actual is not None
        if not has_data:
            text.append("No released figures yet.", style="#7a7a8a")
            return text
        for label, value in (
            ("Actual   ", event.actual),
            ("Forecast ", event.forecast),
            ("Previous ", event.previous),
        ):
            if value:
                text.append(label, style=_LABEL_STYLE)
                text.append(f"{value}\n", style=_RELEASED_STYLE)
        if event.actual_summary:
            text.append("\n")
            text.append(event.actual_summary, style="#c0c0d0")
        return text

    def update_event(self, event: CalendarEvent) -> None:
        self._event = event
        self.query_one("#cal-event-meta", Static).update(self._build_meta())
        self.query_one("#cal-event-figures", Static).update(self._build_figures())
        self.query_one("#cal-event-status", Static).update(
            Text("Updated.", style=_RELEASED_STYLE)
        )
        self._enable_fetch(True)

    def set_status(self, message: str, *, style: str = "#7a7a8a") -> None:
        self.query_one("#cal-event-status", Static).update(Text(message, style=style))

    def _enable_fetch(self, enabled: bool) -> None:
        if not self._can_fetch:
            return
        self.query_one("#cal-event-fetch", Button).disabled = not enabled

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cal-event-close":
            self.dismiss()
        elif event.button.id == "cal-event-fetch" and self._on_fetch is not None:
            self._enable_fetch(False)
            self.set_status("Fetching released figures…", style="#ffd56b")
            self._on_fetch()
