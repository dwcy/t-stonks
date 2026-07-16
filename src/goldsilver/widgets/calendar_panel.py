from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.calendar_actuals_store import event_key
from goldsilver.data.models_macro import CalendarDay, CalendarEvent, CalendarSnapshot
from goldsilver.data.session import STOCKHOLM, stockholm_now


COMPACT_MAX_EVENTS = 3
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class _CalendarBody(Static):
    """A calendar text block that opens the event carried in the clicked span's meta."""

    def __init__(
        self,
        renderable: object = "",
        *,
        on_pick: Callable[[CalendarEvent], None] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(renderable, **kwargs)  # type: ignore[arg-type]
        self._on_pick = on_pick

    def on_click(self, event: events.Click) -> None:
        style = event.style
        picked = style.meta.get("cal_event") if style is not None else None
        if picked is not None and self._on_pick is not None:
            self._on_pick(picked)
            event.stop()


_BUCKET_HEADER = {
    "today": "Today",
    "upcoming": "Upcoming",
}
_BUCKET_HEADER_STYLE = {
    "today": "bold #e8e8f0",
    "upcoming": "#7a7a8a",
}
_DAY_LABEL_STYLE = {
    "today": "bold #c0c0d0",
    "upcoming": "#5a5a6a",
}
_EVENT_STYLE = {
    "today": "#e0e0e8",
    "upcoming": "#6a6a78",
}
_SOURCE_STYLE = {
    "FED": "#7dcfff",
    "ECB": "#bb9af7",
    "RIKSBANK": "#ffd56b",
    "STOCK": "#9ece6a",
}
_IMPACT_LABEL = {
    "HIGH": "HIGH",
    "MED": "MED ",
    "LOW": "LOW ",
}
_IMPACT_STYLE = {
    "HIGH": "bold #ff6b6b",
    "MED": "#ffd56b",
    "LOW": "#6a6a78",
}
_IMPACT_NONE_LABEL = "·   "
_IMPACT_NONE_STYLE = "#5a5a6a"
_RELEASED_STYLE = "#7dff8c"
_TITLE_MAX = 34


class CalendarPanel(Horizontal):
    snapshot: reactive[CalendarSnapshot | None] = reactive(None)
    now_stk: reactive[datetime] = reactive(stockholm_now)

    def __init__(
        self,
        *,
        on_event_selected: Callable[[CalendarEvent], None] | None = None,
    ) -> None:
        super().__init__()
        self.border_title = "Macro Calendar"
        self._compact: bool = False
        self._on_event_selected = on_event_selected
        self._fetching: set[str] = set()
        self._spinner_frame = 0
        self._spinner_timer = None

    def _pick_event(self, event: CalendarEvent) -> None:
        if self._on_event_selected is not None:
            self._on_event_selected(event)

    def apply_fetch_started(self, key: str) -> None:
        self._fetching.add(key)
        self._start_spinner()
        self._refresh_body()

    def apply_fetch_finished(self, key: str, ok: bool) -> None:
        self._fetching.discard(key)
        if not self._fetching:
            self._stop_spinner()
        self._refresh_body()

    def _start_spinner(self) -> None:
        if self._spinner_timer is None:
            self._spinner_timer = self.set_interval(0.12, self._tick_spinner)

    def _stop_spinner(self) -> None:
        if self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None

    def _tick_spinner(self) -> None:
        self._spinner_frame = (self._spinner_frame + 1) % len(_SPINNER_FRAMES)
        self._refresh_body()

    def on_unmount(self) -> None:
        self._stop_spinner()

    def compose(self) -> ComposeResult:
        for bucket in ("today", "upcoming"):
            with VerticalScroll(classes=f"calendar-section -{bucket}"):
                yield _CalendarBody(
                    "loading…",
                    id=f"cal-{bucket}",
                    classes="calendar-body",
                    on_pick=self._pick_event,
                )
        yield _CalendarBody(
            "loading…",
            id="cal-compact",
            classes="calendar-compact",
            on_pick=self._pick_event,
        )

    def on_mount(self) -> None:
        self.set_interval(60.0, self._tick_clock)
        self._refresh_body()

    def apply_snapshot(self, snapshot: CalendarSnapshot) -> None:
        self.snapshot = snapshot

    def watch_snapshot(self, _: CalendarSnapshot | None) -> None:
        self._refresh_body()

    def watch_now_stk(self, _: datetime) -> None:
        self._refresh_body()

    def _tick_clock(self) -> None:
        self.now_stk = stockholm_now()

    def _refresh_body(self) -> None:
        snapshot = self.snapshot
        compact = snapshot is not None and self._is_today_empty(snapshot)
        self._apply_compact_layout(compact)
        if compact:
            assert snapshot is not None
            body = self.query_one("#cal-compact", _CalendarBody)
            body.update(self._render_compact(snapshot))
        else:
            for bucket in ("today", "upcoming"):
                body = self.query_one(f"#cal-{bucket}", _CalendarBody)
                if snapshot is None:
                    body.update(Text("loading…", style="#7a7a8a"))
                else:
                    body.update(self._render_bucket(snapshot, bucket))
        if snapshot is not None:
            self._update_fetched_marker(snapshot)

    @staticmethod
    def _impact_cell(importance: str | None) -> tuple[str, str]:
        if importance in _IMPACT_LABEL:
            return _IMPACT_LABEL[importance], _IMPACT_STYLE[importance]
        return _IMPACT_NONE_LABEL, _IMPACT_NONE_STYLE

    @staticmethod
    def _is_today_empty(snapshot: CalendarSnapshot) -> bool:
        for day in snapshot.days:
            if day.bucket == "today" and day.events:
                return False
        return True

    def _apply_compact_layout(self, compact: bool) -> None:
        if compact == self._compact:
            return
        self._compact = compact
        if compact:
            self.add_class("-compact")
        else:
            self.remove_class("-compact")

    def _render_compact(self, snapshot: CalendarSnapshot) -> Text:
        upcoming_events: list[tuple[CalendarDay, CalendarEvent]] = []
        for day in snapshot.days:
            if day.bucket != "upcoming":
                continue
            for event in day.events:
                upcoming_events.append((day, event))
                if len(upcoming_events) >= COMPACT_MAX_EVENTS:
                    break
            if len(upcoming_events) >= COMPACT_MAX_EVENTS:
                break

        text = Text()
        text.append("No events today", style="#a0a0b0")
        if not upcoming_events:
            text.append("  ·  no upcoming events", style="dim #5a5a6a")
            return text
        text.append("  ·  next: ", style="#7a7a8a")
        for i, (day, event) in enumerate(upcoming_events):
            if i > 0:
                text.append("  ·  ", style="#5a5a6a")
            span_start = len(text)
            day_label = day.date.strftime("%a")
            time_label = (
                "--:--"
                if event.all_day
                else (event.scheduled_time.astimezone(STOCKHOLM).strftime("%H:%M"))
            )
            text.append(f"{day_label} {time_label} ", style="#c0c0d0")
            imp_label, imp_style = self._impact_cell(event.importance)
            text.append(f"{imp_label} ", style=imp_style)
            text.append(
                f"{event.source} ",
                style=_SOURCE_STYLE.get(event.source, "#c0c0d0"),
            )
            title = event.title if len(event.title) <= 40 else event.title[:37] + "…"
            text.append(title, style="#e0e0e8")
            self._tag_event(text, span_start, len(text), event)
        return text

    def _update_fetched_marker(self, snapshot: CalendarSnapshot) -> None:
        local = snapshot.fetched_at.astimezone()
        if snapshot.status == "stale":
            marker = f"stale since {local.strftime('%H:%M:%S')}"
        elif snapshot.status == "unavailable":
            marker = "calendar unavailable"
        else:
            marker = f"fetched {local.strftime('%H:%M:%S')}"
        self.border_subtitle = marker

    def _render_bucket(self, snapshot: CalendarSnapshot, bucket: str) -> Text:
        days = [d for d in snapshot.days if d.bucket == bucket and d.events]
        text = Text()
        if bucket == "today":
            header = f"Today ({self.now_stk.strftime('%a %d %b')})"
        else:
            header = _BUCKET_HEADER[bucket]
        text.append(f"{header}\n", style=_BUCKET_HEADER_STYLE[bucket])
        if not days:
            text.append("  (no events)\n", style="#5a5a6a")
            return text
        for day in days:
            day_label = None if bucket == "today" else day.date.strftime("%a %d %b")
            for event in day.events:
                self._render_event(text, bucket, event, day_label=day_label)
        return text

    def _render_event(
        self,
        text: Text,
        bucket: str,
        event: CalendarEvent,
        day_label: str | None = None,
    ) -> None:
        time_label = (
            "--:--"
            if event.all_day
            else (event.scheduled_time.astimezone(STOCKHOLM).strftime("%H:%M"))
        )
        passed = (
            bucket == "today"
            and not event.all_day
            and (
                event.scheduled_time
                < self.now_stk.astimezone(event.scheduled_time.tzinfo)
            )
        )
        base_style = _EVENT_STYLE[bucket]
        time_style = "dim " + base_style if passed else base_style
        title_style = ("dim " if passed else "") + base_style
        source_style = (
            "dim " + _SOURCE_STYLE[event.source]
            if passed
            else _SOURCE_STYLE[event.source]
        )
        imp_label, imp_style = self._impact_cell(event.importance)
        if passed:
            imp_style = "dim " + imp_style

        row_start = len(text)
        if day_label is not None:
            text.append(f"  {day_label} ", style=_DAY_LABEL_STYLE[bucket])
            text.append(f"{time_label} ", style=time_style)
        else:
            text.append(f"  {time_label} ", style=time_style)
        text.append(f"{imp_label} ", style=imp_style)
        text.append(f"{event.source:<8} ", style=source_style)
        title = (
            event.title
            if len(event.title) <= _TITLE_MAX
            else event.title[: _TITLE_MAX - 3] + "..."
        )
        text.append(title, style=title_style)
        suffix = self._released_suffix(event)
        if suffix is not None:
            text.append(suffix, style=("dim " if passed else "") + _RELEASED_STYLE)
        elif event_key(event) in self._fetching:
            frame = _SPINNER_FRAMES[self._spinner_frame]
            text.append(f"  {frame} fetching…", style="#ffd56b")
        self._tag_event(text, row_start, len(text), event)
        text.append("\n", style=title_style)

    @staticmethod
    def _tag_event(text: Text, start: int, end: int, event: CalendarEvent) -> None:
        # STOCK events (earnings / ex-dividend / pay dates) are display-only — unlike
        # macro releases, there's no detail/actuals view to open, so leave them untagged.
        if end > start and event.source != "STOCK":
            text.stylize(Style(meta={"cal_event": event}), start, end)

    @staticmethod
    def _released_suffix(event: CalendarEvent) -> str | None:
        if event.status != "RELEASED" and event.actual is None:
            return None
        parts: list[str] = []
        if event.actual:
            parts.append(f"act {event.actual}")
        if event.forecast:
            parts.append(f"fc {event.forecast}")
        if event.previous:
            parts.append(f"prev {event.previous}")
        if not parts:
            return None
        return "  " + " / ".join(parts)
