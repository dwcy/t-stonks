from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from rich.text import Text
from textual import events
from textual.widgets import Static

from goldsilver.data.session import STOCKHOLM, stockholm_now


NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class TimelineEvent:
    label: str
    local_time: time
    tone: str
    note: str


@dataclass(frozen=True)
class TimelineSpan:
    start: time
    end: time
    tone: str
    label: str


BAR_COLOR = {
    "normal": "#7dff8c",
    "active": "#ffd56b",
    "intense": "#ff6b6b",
}

BAR_HOVER_COLOR = {
    "normal": "#b8ffc1",
    "active": "#ffe99a",
    "intense": "#ff9f9f",
}

TONE_LABEL = {
    "normal": "low",
    "active": "high",
    "intense": "intense",
}


class MarketTimeline(Static):
    """One-row guide to the normal Stockholm / US market rhythm."""

    def __init__(self) -> None:
        super().__init__("")
        self.add_class("market-timeline")
        self._hover_span_index: int | None = None

    def on_mount(self) -> None:
        self._redraw()
        self.set_interval(60, self._redraw)

    def render(self) -> Text:
        return build_timeline_text(
            stockholm_now(),
            width=max(self.size.width, 72),
            hover_span_index=self._hover_span_index,
        )

    def _redraw(self) -> None:
        self.update(self.render())

    def on_mouse_move(self, event: events.MouseMove) -> None:
        offset = event.get_content_offset(self)
        x = event.x if offset is None else offset.x
        day = stockholm_now().date()
        span_index = span_index_at_x(day, x, self.size.width)
        if span_index == self._hover_span_index:
            return
        self._hover_span_index = span_index
        self.tooltip = hover_tooltip(day, span_index)
        self._redraw()

    def on_leave(self, event: events.Leave) -> None:
        if event.node is not self:
            return
        if self._hover_span_index is None:
            return
        self._hover_span_index = None
        self.tooltip = None
        self._redraw()


def build_timeline_text(
    now: datetime,
    *,
    width: int = 96,
    hover_span_index: int | None = None,
) -> Text:
    local_now = now.astimezone(STOCKHOLM)
    day = local_now.date()
    end = timeline_end(day)
    bar_width = timeline_bar_width(width)

    text = Text()
    text.append("08:15 ", style="#7a7a8a")
    append_timeline_bar(
        text,
        day,
        local_now,
        width=bar_width,
        hover_span_index=hover_span_index,
    )
    text.append(f" {end.strftime('%H:%M')}", style="#7a7a8a")
    return text


def append_timeline_bar(
    text: Text,
    day: date,
    now: datetime,
    *,
    width: int,
    hover_span_index: int | None = None,
) -> None:
    spans = timeline_spans(day)
    start_min = _minute_of_day(time(8, 15))
    end_min = _minute_of_day(timeline_end(day))
    total = end_min - start_min
    now_local = now.astimezone(STOCKHOLM)
    current_start = _minute_of_day(now_local.replace(minute=0).time())
    current_end = current_start + 60

    for index in range(width):
        cell_start = start_min + total * index / width
        cell_end = start_min + total * (index + 1) / width
        mid = (cell_start + cell_end) / 2
        span_index = span_index_at_minute(spans, mid)
        span = spans[span_index]
        tone = span.tone
        in_current_hour = cell_start < current_end and cell_end > current_start
        if in_current_hour:
            text.append(" ", style="on #8ab4ff")
        elif span_index == hover_span_index:
            text.append(" ", style=f"on {BAR_HOVER_COLOR[tone]}")
        else:
            text.append(" ", style=f"on {BAR_COLOR[tone]}")


def timeline_spans(day: date) -> list[TimelineSpan]:
    us_data = _ny_time(day, 8, 30)
    us_first_hour = _ny_time(day, 10, 30)
    cert_close = time(21, 55)
    end = timeline_end(day)
    spans = [
        TimelineSpan(time(8, 15), time(9, 0), "normal", "Certificates warm-up"),
        TimelineSpan(time(9, 0), time(10, 0), "intense", "Stockholm open"),
        TimelineSpan(time(10, 0), time(13, 0), "normal", "Midday low activity"),
        TimelineSpan(time(13, 0), us_data, "active", "US build-up"),
        TimelineSpan(us_data, us_first_hour, "intense", "US data/open shock"),
        TimelineSpan(us_first_hour, time(17, 30), "active", "US first trend"),
        TimelineSpan(time(17, 30), cert_close, "normal", "After Stockholm close"),
        TimelineSpan(cert_close, end, "active", "US close"),
    ]
    return [
        span
        for span in spans
        if _minute_of_day(span.start) < _minute_of_day(span.end)
    ]


def tone_at(spans: list[TimelineSpan], minute: float) -> str:
    return spans[span_index_at_minute(spans, minute)].tone if spans else "normal"


def span_index_at_minute(spans: list[TimelineSpan], minute: float) -> int:
    for index, span in enumerate(spans):
        if _minute_of_day(span.start) <= minute < _minute_of_day(span.end):
            return index
    return max(len(spans) - 1, 0)


def span_index_at_x(day: date, x: int, width: int) -> int | None:
    bar_start = len("08:15 ")
    bar_width = timeline_bar_width(width)
    if x < bar_start or x >= bar_start + bar_width:
        return None
    start_min = _minute_of_day(time(8, 15))
    end_min = _minute_of_day(timeline_end(day))
    minute = start_min + (end_min - start_min) * (x - bar_start + 0.5) / bar_width
    return span_index_at_minute(timeline_spans(day), minute)


def hover_tooltip(day: date, span_index: int | None) -> str | None:
    if span_index is None:
        return None
    spans = timeline_spans(day)
    if span_index < 0 or span_index >= len(spans):
        return None
    span = spans[span_index]
    tone = TONE_LABEL[span.tone]
    return (
        f"{span.label}: {tone} "
        f"{span.start.strftime('%H:%M')}-{span.end.strftime('%H:%M')}"
    )


def timeline_bar_width(width: int) -> int:
    return max(24, width - len("08:15  22:00"))


def timeline_end(day: date) -> time:
    us_close = _ny_time(day, 16, 0)
    cert_close = time(21, 55)
    return max(us_close, cert_close)


def timeline_events(day: date) -> list[TimelineEvent]:
    return [
        TimelineEvent("cert", time(8, 15), "normal", "open"),
        TimelineEvent("09-10", time(9, 0), "intense", "STO open"),
        TimelineEvent("10-13", time(10, 0), "normal", "low"),
        TimelineEvent("13-14", time(13, 0), "active", "high"),
        TimelineEvent("US data", _ny_time(day, 8, 30), "intense", "macro"),
        TimelineEvent("US cash", _ny_time(day, 9, 30), "intense", "open"),
        TimelineEvent("US 1h", _ny_time(day, 10, 30), "active", "trend"),
        TimelineEvent("STO", time(17, 30), "active", "close"),
        TimelineEvent("cert", time(21, 55), "normal", "close"),
        TimelineEvent("US", _ny_time(day, 16, 0), "active", "close"),
    ]


def current_tone(events: list[TimelineEvent], now: time) -> str | None:
    tone: str | None = None
    for event in sorted(events, key=lambda item: item.local_time):
        if now < event.local_time:
            return tone
        tone = event.tone
    return tone


def _ny_time(day: date, hour: int, minute: int) -> time:
    ny_dt = datetime.combine(day, time(hour, minute), tzinfo=NEW_YORK)
    return ny_dt.astimezone(STOCKHOLM).time().replace(second=0, microsecond=0)


def _minute_of_day(value: time) -> int:
    return value.hour * 60 + value.minute
