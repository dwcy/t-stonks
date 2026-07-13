from __future__ import annotations

from datetime import datetime, time

from goldsilver.data.session import STOCKHOLM
from goldsilver.widgets.market_timeline import (
    build_timeline_text,
    current_tone,
    hover_tooltip,
    span_index_at_x,
    timeline_events,
)


def test_summer_timeline_uses_stockholm_local_market_markers() -> None:
    text = build_timeline_text(
        datetime(2026, 7, 13, 12, 0, tzinfo=STOCKHOLM),
        width=120,
    )
    plain = text.plain

    assert plain.startswith("08:15 ")
    assert "22:00" in plain
    assert "NOW 12:00-13:00" not in plain
    assert "US cash open" not in plain
    assert "low" not in plain
    assert "high" not in plain
    assert "intense" not in plain
    assert any("#8ab4ff" in str(span.style) for span in text.spans)

    day = datetime(2026, 7, 13, tzinfo=STOCKHOLM).date()
    events = {event.label: event.local_time for event in timeline_events(day)}
    assert events["US data"] == time(14, 30)
    assert events["US cash"] == time(15, 30)
    assert events["US 1h"] == time(16, 30)
    assert events["US"] == time(22, 0)

    first_bar_cell = len("08:15 ")
    tip = hover_tooltip(day, span_index_at_x(day, first_bar_cell, 120))
    assert tip == "Certificates warm-up: low 08:15-09:00"
    assert span_index_at_x(day, 0, 120) is None


def test_timeline_marks_open_and_us_data_windows_as_intense() -> None:
    events = timeline_events(datetime(2026, 7, 13, tzinfo=STOCKHOLM).date())

    assert current_tone(events, time(9, 30)) == "intense"
    assert current_tone(events, time(11, 0)) == "normal"
    assert current_tone(events, time(13, 30)) == "active"
    assert current_tone(events, time(14, 45)) == "intense"
    assert current_tone(events, time(16, 45)) == "active"
