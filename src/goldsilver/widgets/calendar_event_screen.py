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
_EXPECTED_STYLE = "#ffd56b"
_DIR_STYLE = {"bullish": "#7dff8c", "bearish": "#ff6b6b", "neutral": "#9a9aa8"}
_DIR_ARROW = {"bullish": "▲", "bearish": "▼", "neutral": "→"}
_SURPRISE_LABEL = {
    "above": "above forecast",
    "below": "below forecast",
    "inline": "in line",
    "na": "",
}
_SURPRISE_STYLE = {"above": "#ffd56b", "below": "#ffd56b", "inline": "#9a9aa8"}


class CalendarEventScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        event: CalendarEvent,
        *,
        on_fetch: Callable[[], None] | None = None,
        can_fetch: bool = False,
        fetch_label: str = "Fetch now",
        fetch_pending_message: str = "Fetching released figures…",
    ) -> None:
        super().__init__()
        self._event = event
        self._on_fetch = on_fetch
        self._can_fetch = can_fetch
        self._fetch_label = fetch_label
        self._fetch_pending_message = fetch_pending_message

    def compose(self) -> ComposeResult:
        with Container(id="cal-event-dialog"):
            yield Static(self._event.title, id="cal-event-title")
            yield Static(self._build_meta(), id="cal-event-meta")
            yield Static(self._build_figures(), id="cal-event-figures")
            yield Static(self._build_analysis(), id="cal-event-analysis")
            yield Static("", id="cal-event-status")
            with Horizontal(id="cal-event-actions"):
                if self._can_fetch:
                    yield Button(
                        self._fetch_label, id="cal-event-fetch", variant="primary"
                    )
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
        has_actual = event.actual is not None
        if not (has_actual or event.forecast or event.previous):
            text.append("No forecast or released figures yet.", style="#7a7a8a")
            return text
        value_style = _RELEASED_STYLE if has_actual else _EXPECTED_STYLE
        rows = [("Forecast ", event.forecast), ("Previous ", event.previous)]
        if has_actual:
            rows.insert(0, ("Actual   ", event.actual))
        for label, value in rows:
            if value:
                text.append(label, style=_LABEL_STYLE)
                text.append(f"{value}\n", style=value_style)
        summary = event.actual_summary if has_actual else event.expected_summary
        if summary:
            text.append("\n")
            text.append(summary, style="#c0c0d0")
        return text

    def _build_analysis(self) -> Text:
        analysis = self._event.analysis
        text = Text()
        if analysis is None:
            return text
        is_preview = self._event.is_expectation
        heading = "Expected impact (if on consensus)" if is_preview else "Impact read"
        text.append(f"\n{heading}\n", style=_LABEL_STYLE)
        surprise = _SURPRISE_LABEL.get(analysis.surprise, "")
        if surprise and not is_preview:
            text.append("vs consensus  ", style=_LABEL_STYLE)
            text.append(
                f"{surprise}\n",
                style=_SURPRISE_STYLE.get(analysis.surprise, _VALUE_STYLE),
            )
        for label, direction in (
            ("Gold   ", analysis.gold),
            ("Silver ", analysis.silver),
            ("USD    ", analysis.usd),
        ):
            text.append(label, style=_LABEL_STYLE)
            text.append(
                f"{_DIR_ARROW[direction]} {direction}\n", style=_DIR_STYLE[direction]
            )
        if analysis.rationale:
            text.append("\n")
            text.append(analysis.rationale, style="#c0c0d0")
        return text

    def update_event(self, event: CalendarEvent) -> None:
        self._event = event
        self.query_one("#cal-event-meta", Static).update(self._build_meta())
        self.query_one("#cal-event-figures", Static).update(self._build_figures())
        self.query_one("#cal-event-analysis", Static).update(self._build_analysis())
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
            self.set_status(self._fetch_pending_message, style="#ffd56b")
            self._on_fetch()
