from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from goldsilver.data.models_macro import CalendarDay, CalendarEvent, CalendarSnapshot
from goldsilver.data.session import STOCKHOLM, stockholm_now


COMPACT_MAX_EVENTS = 3


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
}


class CalendarPanel(Horizontal):
    snapshot: reactive[CalendarSnapshot | None] = reactive(None)
    now_stk: reactive[datetime] = reactive(stockholm_now)

    def __init__(self) -> None:
        super().__init__()
        self.border_title = "Macro Calendar"
        self._compact: bool = False

    def compose(self) -> ComposeResult:
        for bucket in ("today", "upcoming"):
            with VerticalScroll(classes=f"calendar-section -{bucket}"):
                yield Static("loading…", id=f"cal-{bucket}", classes="calendar-body")
        yield Static(
            "loading…",
            id="cal-compact",
            classes="calendar-compact",
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
            body = self.query_one("#cal-compact", Static)
            body.update(self._render_compact(snapshot))
        else:
            for bucket in ("today", "upcoming"):
                body = self.query_one(f"#cal-{bucket}", Static)
                if snapshot is None:
                    body.update(Text("loading…", style="#7a7a8a"))
                else:
                    body.update(self._render_bucket(snapshot, bucket))
        if snapshot is not None:
            self._update_fetched_marker(snapshot)

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
            day_label = day.date.strftime("%a")
            time_label = (
                "--:--"
                if event.all_day
                else (event.scheduled_time.astimezone(STOCKHOLM).strftime("%H:%M"))
            )
            text.append(f"{day_label} {time_label} ", style="#c0c0d0")
            text.append(
                f"{event.source} ",
                style=_SOURCE_STYLE.get(event.source, "#c0c0d0"),
            )
            title = event.title if len(event.title) <= 40 else event.title[:37] + "…"
            text.append(title, style="#e0e0e8")
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

        if day_label is not None:
            text.append(f"  {day_label} ", style=_DAY_LABEL_STYLE[bucket])
            text.append(f"{time_label} ", style=time_style)
        else:
            text.append(f"  {time_label} ", style=time_style)
        text.append(f"{event.source:<8} ", style=source_style)
        title = event.title if len(event.title) <= 40 else event.title[:37] + "..."
        text.append(f"{title}\n", style=title_style)
